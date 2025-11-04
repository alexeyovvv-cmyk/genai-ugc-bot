## Что лежит в репозитории

- `.env.example` — шаблон переменных окружения (скопируй в `.env`, впиши ключи Shotstack).
- `source_env.sh` — подхватывает `.env` в текущей сессии.
- `requirements.txt` — зависимости Python (`pip install -r requirements.txt`).
- `prepare_overlay.py` — вырезает говорящую голову с альфой и загружает в Shotstack ingest.
- `assemble.py` — отправляет любой JSON-теймлайн в Shotstack (ручной режим).
- `autopipeline.py` — «одна кнопка»: качает ассеты, вырезает голову, строит субтитры, применяет блоки, обновляет шаблоны и (по желанию) рендерит видео.
- `render/templates/presets/talking_head_*.json` — базовые шаблоны пяти сценариев (overlay, circle, basic, mix_overlay, mix_circle). В каждом есть заготовка из трёх субтитров, позиция головы и фон.
- `render/timeline/config/blocks.json` — конфигурация дополнительных блоков для интро/аутро и оверлеев.
- `build/` — сюда автопайплайн складывает сгенерированные спецификации (папка под каждую запускную сессию).

## Быстрый старт

```bash
cp .env.example .env   # при первом запуске, впиши ключ Shotstack
source ./source_env.sh
pip install -r requirements.txt
```

## Ручной режим (если нужен контроль)

1. **Голова с альфой**
   ```bash
   python3 prepare_overlay.py \
     --input-url "<ссылка>" \
     --output talking_head_alpha.mov \
     --container mov \
     --engine rembg \
     --rembg-alpha-matting
   ```
   Скрипт скачает исходник, вырежет фон, сохранит локальный MOV/WebM и вернёт публичный Shotstack URL.

2. **Обнови JSON** — подставь новые `src` (фон/голова/оверлей), при необходимости поправь блок `subtitles` (`start`, `length`, `text`).

3. **Собери**  
   ```bash
   python3 assemble.py talking_head_overlay.json
   ```
   Получишь ссылку на mp4.

## Автопайплайн (рекомендуется)

```bash
source ./source_env.sh
python3 autopipeline.py \
  --background-url "<ссылка на фон>" \
  --head-url "<ссылка на голову>" \
  [--subtitles subtitles.json] \
  [--transcript "текст" | --transcript-file text.txt] \
  [--subtitles-enabled auto|manual|none] \
  [--blocks-config render/timeline/config/blocks.json] \
  [--intro-url "<intro.mp4>" --intro-length 2.5 --intro-templates overlay,circle] \
  [--outro-url "<outro.mp4>" --outro-length 2.5 --outro-templates overlay,circle] \
  [--templates overlay,circle,...] \
  [--background-video-length auto|fixed] \
  [--subtitle-theme light|yellow_on_black] \
  [--no-circle-auto-center] \
  [--no-render]
```

### Что делает скрипт
- скачивает фон и голову, анализирует через ffprobe и определяет `fit` (cover/contain) и тип (image/video);
- генерирует прямоугольный/круглый оверлей (rembg) с автоматической центровкой круга по маске (если не указан `--no-circle-auto-center`);
- подстраивает длительность фона:
  - `--background-video-length auto` (по умолчанию): подгоняет под голову через speed
  - `--background-video-length fixed`: оставляет оригинальную длительность фона
- **субтитры**:
  - `--subtitles-enabled auto` (по умолчанию): берёт `--subtitles`, иначе строит по `--transcript` через `ffmpeg silencedetect`; если ни того ни другого — подставляет дефолтные три реплики;
  - `manual`: использовать только `--subtitles`, иначе блок удаляется;
  - `none`: в итоговых шаблонах субтитров не будет;
  - выбор темы через `--subtitle-theme light|yellow_on_black`;
- применяет `render/timeline/config/blocks.json` (опциональные блоки: интро, аутро, дополнительные оверлеи) и/или параметры `--intro-*`/`--outro-*` (можно настроить на лету без отдельного файла);
- сохраняет готовые спецификации в `build/auto_*`;
- без `--no-render` сразу отправляет их в Shotstack и печатает ссылки на mp4.

### Пример `blocks.json`
```json
{
  "overlay": {
    "prepend_clips": [
      {
        "type": "video",
        "src": "https://example.com/brand-intro.mp4",
        "length": 2.5,
        "fit": "contain",
        "transition": "fade"
      }
    ],
    "append_clips": [
      {
        "type": "video",
        "src": "https://example.com/brand-outro.mp4",
        "length": 2.5,
        "fit": "contain",
        "transition": "fade"
      }
    ]
  }
}
```
Можно добавить секции для `circle`, `basic`, `mix_basic_overlay`, `mix_basic_circle`, а также `append_overlays` (доп. слои поверх).

Чтобы не хранить файл, можно передать интро/аутро прямо в командной строке:

```bash
python3 autopipeline.py ... \
  --intro-url "https://example.com/intro.mp4" --intro-length 2.0 --intro-templates mix_basic_circle \
  --outro-url "https://example.com/outro.mp4" --outro-length 3.0
```

Если нужен только интро (без аутро) — просто опусти `--outro-*` (и наоборот).

## Особенности

- Автоматические субтитры рендерятся шрифтом **Helvetica Neue / Helvetica / Arial**, белый текст на полупрозрачном чёрном фоне (`rgba(0,0,0,0.75)`), тень добавлена.
- Голова в mix-сценариях: первые 3 секунды — fullscreen, дальше звук остаётся, а видео прячется за кадром (`scale 0.001`), фон идёт в `contain`.
- Бот/CLI может собирать сценарий «под ключ», пользователю достаточно дать две ссылки (фон + голова), текст или файл субтитров и выбрать пресет/блоки. Всё остальное делает `autopipeline.py`.

## Полезные команды

```bash
# Сгенерировать пакет шаблонов без рендера
python3 autopipeline.py --background-url ... --head-url ... --no-render

# Прогнать только сценарий overlay
python3 autopipeline.py --background-url ... --head-url ... --templates overlay

# Без субтитров
python3 autopipeline.py ... --subtitles-enabled none

# Проверить JSON
python3 -m json.tool talking_head_overlay.json
```
