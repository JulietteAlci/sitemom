"""Code 128 (set B) barcodes as inline SVG, so kit references can be scanned on return."""
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# Bar/space widths for Code 128 symbols 0–106 (106 = stop, with its final bar).
PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
]
START_B, STOP = 104, 106


def code128_widths(text: str) -> str:
    values = [ord(char) - 32 for char in text if 32 <= ord(char) < 127]
    checksum = (START_B + sum(position * value for position, value in enumerate(values, start=1))) % 103
    return "".join(PATTERNS[symbol] for symbol in [START_B, *values, checksum, STOP])


@register.simple_tag
def barcode_svg(text: str, height: int = 60, module: float = 2) -> str:
    x, bars = 10 * module, []
    for index, width in enumerate(code128_widths(text)):
        width = int(width) * module
        if index % 2 == 0:  # even positions are bars
            bars.append(f'<rect x="{x:g}" y="0" width="{width:g}" height="{height}"/>')
        x += width
    total = x + 10 * module
    return mark_safe(
        f'<svg class="barcode" viewBox="0 0 {total:g} {height}" width="{total:g}" height="{height}" '
        f'role="img" aria-label="{escape(text)}" preserveAspectRatio="none"><g fill="#000">{"".join(bars)}</g></svg>'
    )
