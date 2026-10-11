from pathlib import Path

from render import FONT_SPECS, UrduRenderer, calibrate_pixel_size, visible_bbox


def test_fonts_render_nonblank_rtl_text():
    for spec in FONT_SPECS.values():
        if not spec.path.exists():
            continue
        size, _ = calibrate_pixel_size(spec.path)
        image = UrduRenderer(spec.path, size).render("پاکستان کی کتاب")
        bbox = visible_bbox(image)
        assert bbox is not None
        assert 0 < bbox[0] < bbox[2] < image.width
        assert 0 < bbox[1] < bbox[3] < image.height
