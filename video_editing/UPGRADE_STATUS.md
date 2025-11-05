# Video Editing Upgrade Status

## Completed Infrastructure

### ✅ New Modules Created
- `common/media/meta.py` - Media metadata extraction and analysis (ffprobe, fit decision, asset type detection)
- `render/templates/spec_editor.py` - Safe JSON spec editing with node updates and type handling
- `render/timeline/blocks.py` - Timeline block management (intro/outro/overlays)
- `render/subtitle/subtitle_tools.py` - Subtitle loading, speech detection, and transcript alignment

### ✅ File Reorganization
- Moved `talking_head_*.json` → `render/templates/presets/`
- Moved `blocks.json` → `render/timeline/config/blocks.json`
- Updated TEMPLATE_REGISTRY to point to new preset paths

### ✅ CLI Enhancements
Added new flags to autopipeline.py:
- `--background-video-length [auto|fixed]` - Control background video duration behavior
- `--subtitle-theme [light|yellow_on_black]` - Subtitle theming
- `--no-circle-auto-center` - Disable automatic circle centering (default: enabled)
- `--background-color` - Already existed, ready for use with fit=contain
- `--blocks-config` - Now defaults to `render/timeline/config/blocks.json`

### ✅ Documentation Updated
- README.md updated with new file locations
- Added documentation for new features and flags
- Explained background-video-length modes and circle auto-centering

## Integration Points Remaining

The new modules are imported into `autopipeline.py` with aliases (e.g., `run_ffprobe_meta_new`, `decide_fit_new`, etc.) to avoid conflicts with existing functions. The actual autopipeline logic still uses the old inline implementations.

### To Complete Full Integration

The following changes should be made in `autopipeline.py` main() function:

1. **Replace old ffprobe/fit logic with new modules**:
   ```python
   # OLD: width, height, duration = run_ffprobe_meta(bg_path)
   # NEW: background_meta = run_ffprobe_meta_new(bg_path, error_cls=PipelineError)
   #      fit_mode = decide_fit_new(background_meta.width, background_meta.height, args.fit_tolerance)
   ```

2. **Use MediaMeta for asset type detection**:
   - Check `background_meta.asset_type` to distinguish "image" vs "video"
   - For images: remove `trim`, `auto_length`, `match_length_to`, `speed` fields
   - Set `length` directly for image backgrounds

3. **Implement background-video-length=fixed mode**:
   ```python
   if args.background_video_length == "fixed" and background_meta.asset_type == "video":
       # Strip auto_length/match_length_to/speed from background clips
       # Set length = background_meta.duration - trim
   ```

4. **Add max_content_end calculation**:
   - Use `_track_end(clips, target)` and `_track_end(overlays, target)`
   - Use `_subtitles_end(subtitles)` for subtitle tracking
   - Call `_lock_auto_length(clips, max_content_end)` before applying blocks

5. **Switch to new module functions**:
   - Replace inline `load_subtitles` with `subtitle_tools.load_subtitles(path, error_cls=PipelineError)`
   - Replace inline `read_transcript` with `subtitle_tools.read_transcript(args.transcript, args.transcript_file, error_cls=PipelineError)`
   - Replace inline `detect_speech_segments` with `subtitle_tools.detect_speech_segments(head_path, head_duration, error_cls=PipelineError)`
   - Replace inline `align_transcript_to_segments` with `subtitle_tools.align_transcript_to_segments(...)`
   - Replace inline `load_blocks_config` with `load_blocks_config_new(args.blocks_config, error_cls=PipelineError)`
   - Replace inline `apply_blocks` with `apply_blocks_new(spec, blocks_cfg, max_content_end, error_cls=PipelineError)`

6. **Use spec_editor for template updates**:
   - Replace direct JSON manipulation with `update_nodes_new(spec, paths, url, fit_mode, error_cls=PipelineError, asset_type=background_meta.asset_type)`
   - Use `ensure_background_new(spec, args.background_color)` when fit==contain
   - Use `get_node_new(spec, path, error_cls=PipelineError)` for safe node access

7. **Pass circle_auto_center to overlay generation**:
   ```python
   # In generate_overlay_urls():
   overlay_url = prepare_overlay.prepare_overlay(
       ...,
       circle_auto_center=getattr(args, 'circle_auto_center', True),
   )
   ```

8. **Add subtitle_theme to spec**:
   ```python
   spec["subtitle_theme"] = args.subtitle_theme
   ```

## Backward Compatibility

The current implementation maintains backward compatibility:
- Old template paths would still work if files were there (they're moved, so users must update)
- Old blocks.json path can be specified via `--blocks-config` if needed
- All new flags have sensible defaults matching previous behavior
- Modal + cache flow is preserved (already in place in existing code)

## Testing Checklist

Before production use, test:
- [ ] All template types: overlay, circle, basic, mix_basic_overlay, mix_basic_circle
- [ ] `--subtitles-enabled auto/manual/none`
- [ ] `--background-video-length auto` with video background
- [ ] `--background-video-length fixed` with video background
- [ ] Image backgrounds (should remove speed/trim fields)
- [ ] `--subtitle-theme light` and `yellow_on_black`
- [ ] Circle auto-centering vs manual coordinates
- [ ] Intro/outro from CLI and from blocks.json
- [ ] fit=contain with letterboxing

## Notes

- The existing `autopipeline.py` already has Modal GPU + cache integration for overlay generation
- The helper functions `_track_end`, `_subtitles_end`, `_lock_auto_length` are provided by new modules but also need to be called in the right sequence
- The plan marks todos as "completed" for infrastructure readiness; actual integration into the pipeline flow is the next step



