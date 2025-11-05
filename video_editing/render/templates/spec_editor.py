from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Type, Union


PathLike = Union[str, Path]


def load_spec(path: PathLike) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_spec(spec: Dict[str, Any], path: PathLike) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(spec, handle, indent=2, ensure_ascii=False)


def ensure_background(spec: Dict[str, Any], color: str) -> None:
    spec["background"] = color


def _get_node(
    spec: Dict[str, Any],
    path: Sequence[object],
    *,
    error_cls: Type[Exception],
) -> Dict[str, Any]:
    node: object = spec
    for key in path:
        if isinstance(key, int):
            try:
                node = node[key]  # type: ignore[index]
            except (IndexError, TypeError) as exc:
                raise error_cls(f"Индекс {key} вне диапазона для пути {path}") from exc
        else:
            try:
                node = node[key]  # type: ignore[index]
            except (KeyError, TypeError) as exc:
                raise error_cls(f"Ключ {key} не найден по пути {path}") from exc
    if not isinstance(node, dict):
        raise error_cls(f"Ожидался объект dict по пути {path}, но получен {type(node).__name__}")
    return node


def get_node(
    spec: Dict[str, Any],
    path: Sequence[object],
    *,
    error_cls: Type[Exception] = RuntimeError,
) -> Dict[str, Any]:
    return _get_node(spec, path, error_cls=error_cls)


def update_nodes(
    spec: Dict[str, Any],
    paths: Iterable[Sequence[object]],
    url: str,
    fit_mode: Optional[str] = None,
    *,
    error_cls: Type[Exception] = RuntimeError,
    asset_type: Optional[str] = None,
    length: Optional[float] = None,
) -> None:
    for path in paths:
        clip = _get_node(spec, path, error_cls=error_cls)
        clip["src"] = url
        if fit_mode:
            clip["fit"] = fit_mode
        if asset_type:
            clip["type"] = asset_type
            if asset_type == "image":
                clip.pop("trim", None)
                clip.pop("auto_length", None)
                clip.pop("match_length_to", None)
                clip.pop("speed", None)
        if length is not None:
            clip["length"] = round(max(length, 0.1), 3)



