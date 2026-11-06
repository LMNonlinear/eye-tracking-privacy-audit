"""Produce a two-page overview and the complete report from saved audit results."""
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
import tempfile
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from scripts.render_audit_report import _font, write_pdf_report

INK = colors.HexColor('#253846')
PURPLE = colors.HexColor('#7952a2')
GREEN = colors.HexColor('#238873')
RED = colors.HexColor('#aa2029')
GRAY = colors.HexColor('#dce2e5')
WIDTH, HEIGHT = A4
LEFT, RIGHT = 48, WIDTH - 48


def summarize_results(result):
    """Aggregate saved estimates and decisions; never recompute inference."""
    plan = result['plan']
    excluded = {plan['baseline'], *plan.get('controls', [])}
    panels = OrderedDict()
    for row in result['condition_results']:
        panel = panels.setdefault((row['dataset'], row['evaluator']), {'baseline': [], 'protected': []})
        if row['condition'] == plan['baseline']:
            panel['baseline'].append(float(row['signed_gap_pp']))
        elif row['condition'] not in excluded:
            panel['protected'].append(float(row['signed_gap_pp']))
    changes = {'larger': 0, 'smaller': 0, 'equal': 0}
    for panel in panels.values():
        if len(panel['baseline']) == 1:
            before = abs(panel['baseline'][0])
            for gap in panel['protected']:
                key = 'larger' if abs(gap) > before else 'smaller' if abs(gap) < before else 'equal'
                changes[key] += 1
    secondary = result['secondary_tests']
    groups = [
        ('Residual group gaps', [x for x in secondary if x['endpoint'] == 'residual_rank1']),
        ('Changes from baseline', [x for x in secondary if x['endpoint'] == 'change_from_baseline']),
        ('Mechanism comparisons', result['primary_tests']),
        ('Utility comparisons', result['utility_tests']),
    ]
    decisions = []
    for label, rows in groups:
        if rows:
            decisions.append(dict(label=label, total=len(rows),
                                  passed=sum(x.get('passes_correction') is True for x in rows),
                                  not_passed=sum(x.get('passes_correction') is False for x in rows),
                                  withheld=sum(x.get('passes_correction') is None for x in rows)))
    return dict(panels=panels, changes=changes, decisions=decisions,
                baseline=[v for p in panels.values() for v in p['baseline']],
                protected=[v for p in panels.values() for v in p['protected']])


def _short(value, size=45):
    value = str(value).replace('\n', ' ')
    return value if len(value) <= size else value[:size - 3] + '...'


def summary_findings(summary, result, language='en'):
    """Use bounded prose even for large plans; numerical direction is descriptive."""
    zh = language == 'zh'
    baseline = summary['baseline']
    if baseline:
        low, high = min(baseline), max(baseline)
        if low > 0:
            first = (f'保护前，A组识别率均高于B组，估计差距为{low:.2f}至{high:.2f}个百分点。' if zh else
                     f'Before protection, group A had higher estimated identification rates than group B, with gaps of {low:.2f} to {high:.2f} percentage points.')
        elif high < 0:
            first = (f'保护前，B组识别率均高于A组，估计差距为{abs(high):.2f}至{abs(low):.2f}个百分点。' if zh else
                     f'Before protection, group B had higher estimated identification rates than group A, with gaps of {abs(high):.2f} to {abs(low):.2f} percentage points.')
        else:
            first = (f'保护前，A组减B组的识别率估计差距为{low:.2f}至{high:.2f}个百分点。' if zh else
                     f'Before protection, estimated identification-rate differences (A minus B) ranged from {low:.2f} to {high:.2f} percentage points.')
    else:
        first = '未提供保护前的群体差距。' if zh else 'Baseline group-gap estimates are unavailable.'
    ch = summary['changes']
    total = sum(ch.values())
    if total:
        second = (f'保护后，与各自基线相比，{total}项设置中{ch["larger"]}项差距数值变大、{ch["smaller"]}项变小、{ch["equal"]}项不变。' if zh else
                  f'After protection, gaps were numerically larger in {ch["larger"]} of {total} matched settings, smaller in {ch["smaller"]}, and unchanged in {ch["equal"]}, relative to their own baselines.')
    else:
        second = '没有可匹配的保护前后差距。' if zh else 'Matched before-and-after gap estimates are unavailable.'
    if not zh:
        if baseline and low == high:
            first = first.replace(f'{low:.2f} to {high:.2f}', f'{low:.2f}').replace(
                f'{abs(high):.2f} to {abs(low):.2f}', f'{abs(low):.2f}')
        if ch['equal'] == 0:
            second = second.replace(', and unchanged in 0,', ',')
    return first, second


def _chart_panels(summary):
    """Limit visual rows, retaining the complete range of every remaining panel."""
    panels = list(summary['panels'].items())
    if len(panels) <= 5:
        return [(_short(f'{key[0]} / {key[1]}', 65), values) for key, values in panels]
    shown = [(_short(f'{key[0]} / {key[1]}', 65), values) for key, values in panels[:4]]
    remainder = {'baseline': [], 'protected': []}
    for _, values in panels[4:]:
        for key in remainder:
            remainder[key].extend(values[key])
    shown.append((f'Remaining {len(panels) - 4} dataset/model panels (combined range)', remainder))
    return shown


def write_summary_report(result, destination, language='en', report_font=None):
    """Write exactly two pages with fixed regions and explicit overflow checks."""
    if language not in ('en', 'zh'):
        raise ValueError('Report language must be en or zh')
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('Preserve existing reports; choose a fresh PDF path')
    summary = summarize_results(result)
    font = _font(report_font, language)
    name = font.fontName
    zh = language == 'zh'
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle('Group Privacy Audit - Summary')
    pdf.setAuthor('Group Privacy Audit')

    def paragraph(text, y, size=10, color=INK, max_height=90):
        missing = {ch for ch in str(text) if ord(ch) >= 32 and ord(ch) not in font.face.charWidths}
        if missing:
            raise ValueError('The selected PDF font lacks characters; supply --report-font')
        style = ParagraphStyle('summary', fontName=name, fontSize=size, leading=size * 1.4,
                               textColor=color, wordWrap='CJK' if zh else None)
        block = Paragraph(escape(str(text)), style)
        _, height = block.wrap(RIGHT - LEFT, max_height)
        if height > max_height or y - height < 55:
            raise ValueError('Summary layout exceeds its two-page budget')
        block.drawOn(pdf, LEFT, y - height)
        return y - height - 9

    def footer(page):
        pdf.setFont(name, 8)
        pdf.setFillColor(INK)
        pdf.drawRightString(RIGHT, 29, f'{page} / 2')
        if 'synthetic' in str(result['plan'].get('scope', '')).lower():
            pdf.drawString(LEFT, 29, '本报告为样本，基于仿真数据生成。' if zh else
                           'Sample report generated from simulated data.')

    y = paragraph('群体隐私保护审计 | 汇总报告' if zh else 'Group Privacy Audit | Summary', HEIGHT - 44, 19)
    y = paragraph('主要结果' if zh else 'Main findings', y, 12, GREEN)
    for finding in summary_findings(summary, result, language):
        y = paragraph(finding, y, 14, RED, max_height=100)
    pair = result['plan']['hypotheses'][0]
    y = paragraph(f'A: {_short(pair[0], 65)}    |    B: {_short(pair[1], 65)}', y, 10)
    y = paragraph('数值变化为描述性结果；基线未单独检验。统计支持见第2页。' if zh else
                  'These are descriptive changes in gap magnitude; baseline significance was not tested separately. Statistical support is summarized on page 2.', y, 9)
    y = paragraph('保护前后的群体差距' if zh else 'Group gaps before and after protection', y - 3, 12, GREEN)
    y = paragraph('标记与线段为所测条件的最小值至最大值，不是置信区间；差距为A减B，单位为百分点。' if zh else
                  'Markers and segments show the minimum and maximum observed gaps across settings, not confidence intervals. Gaps are A minus B, in percentage points.', y, 9)
    # A common signed scale preserves reversals and baseline-relative differences.
    values = [0.0, *summary['baseline'], *summary['protected']]
    low, high = min(values), max(values)
    padding = max((high - low) * .08, .5)
    low, high = low - padding, high + padding
    x0, x1 = LEFT + 14, RIGHT - 14
    scale = lambda value: x0 + (value - low) / (high - low) * (x1 - x0)
    pdf.setFont(name, 9)
    pdf.setFillColor(PURPLE)
    pdf.drawString(LEFT, y - 5, '未保护基线' if zh else 'Baseline')
    pdf.setFillColor(GREEN)
    pdf.drawString(LEFT + 160, y - 5, '保护后条件范围' if zh else 'Protected settings: range')
    top = y - 26
    panels = _chart_panels(summary)
    for i, (label, panel) in enumerate(panels):
        row_y = top - i * 47
        pdf.setFillColor(INK)
        pdf.setFont(name, 9)
        pdf.drawString(LEFT, row_y, label)
        pdf.setStrokeColor(GRAY)
        pdf.setDash(2, 2)
        pdf.line(scale(0), row_y - 6, scale(0), row_y - 30)
        pdf.setDash()
        for key, color, dy in [('baseline', PURPLE, 12), ('protected', GREEN, 25)]:
            if not panel[key]:
                continue
            a, b = min(panel[key]), max(panel[key])
            pdf.setStrokeColor(color)
            pdf.setFillColor(color)
            pdf.setLineWidth(2)
            pdf.line(scale(a), row_y - dy, scale(b), row_y - dy)
            pdf.circle(scale(a), row_y - dy, 2.5, fill=1, stroke=0)
            pdf.circle(scale(b), row_y - dy, 2.5, fill=1, stroke=0)
    axis_y = top - len(panels) * 47 + 5
    if axis_y < 100:
        raise ValueError('Summary chart exceeds its two-page budget')
    pdf.setFont(name, 8)
    pdf.setFillColor(INK)
    for i in range(5):
        val = low + (high - low) * i / 4
        pdf.drawCentredString(scale(val), axis_y, f'{val:.1f}')
    paragraph(f'{len(summary["panels"])} dataset/model panels; {len(summary["protected"])} protected settings. '
              'Declared controls are excluded from this overview. All settings and full labels are retained in the detailed report.',
              axis_y - 13, 9, max_height=55)
    footer(1)
    pdf.showPage()

    y = paragraph('群体隐私保护审计 | 统计汇总' if zh else 'Group Privacy Audit | Statistical overview', HEIGHT - 44, 18)
    enabled = bool(result['formal_decisions_enabled'])
    decisions = summary['decisions']
    passed = sum(x['passed'] for x in decisions)
    total = sum(x['total'] for x in decisions)
    lead = (f'在{total}项预设比较中，{passed}项通过多重比较校正。' if zh else
            f'{passed} of {total} planned comparisons passed multiple-comparison correction.') if enabled else (
            '正式统计判决暂不提供；本报告中的估计仅作描述。' if zh else
            'Formal statistical decisions are withheld; the estimates in this report are descriptive.')
    y = paragraph(lead, y, 14, RED)
    y = paragraph('统计支持、未通过与暂不判决分别显示；未通过不能证明群体相等。' if zh else
                  'Supported, not supported and withheld decisions are shown separately. A result that does not pass correction does not establish equal protection.', y, 10)
    for row in decisions:
        y = paragraph(row['label'], y - 3, 11, GREEN)
        bar_y = y - 12
        start = LEFT
        for key, color in [('passed', GREEN), ('not_passed', GRAY), ('withheld', PURPLE)]:
            width = (RIGHT - LEFT) * row[key] / row['total']
            pdf.setFillColor(color)
            pdf.rect(start, bar_y, width, 11, fill=1, stroke=0)
            start += width
        y = paragraph(f'{row["passed"]} supported | {row["not_passed"]} not supported | {row["withheld"]} withheld | {row["total"]} total', bar_y - 5, 9)
    y = paragraph('统计方法与比较族' if zh else 'Method and comparison families', y - 2, 12, GREEN)
    y = paragraph('Repeated scores are averaged within participant, then the five folds receive equal weight. '
                  f'Welch-Satterthwaite approximate t inference uses alpha = {result["plan"].get("alpha", .05):g}. '
                  'Holm correction is applied separately to the mechanism, residual/change, and utility families '
                  f'(sizes: {" / ".join(map(str, result["family_sizes"]))}). '
                  'Residual and baseline-change rows above share one family; the display does not split the correction.', y, 9, max_height=85)
    y = paragraph('解读与报告范围' if zh else 'Interpretation and report scope', y - 2, 12, GREEN)
    y = paragraph('A signed gap change is the protected A-minus-B gap minus its baseline gap. '
                  'This differs from a change in absolute gap magnitude when direction reverses. '
                  'Inference is conditional on fitted models and observed galleries and assumes independent participants. '
                  'Pointwise intervals and all individual p-values are in the detailed report.', y, 9, max_height=80)
    y = paragraph('Plan scope: ' + _short(result['plan'].get('scope', 'Not specified'), 240) +
                  ' (Full note in the detailed report.)', y, 9, max_height=65)
    y = paragraph(f'Calibration: {_short(result["calibration_status"], 80)}. '
                  f'Method: {_short(result["analysis_mode"], 60)}.', y, 8, max_height=40)
    paragraph('完整结果' if zh else 'Complete results: report_detailed.pdf and report.json retain every condition, confidence interval, raw and adjusted p-value, diagnostic annotation and input hash.', y, 9, max_height=45)
    footer(2)
    pdf.save()
    destination.write_bytes(buffer.getvalue())


def write_report_bundle(result, output_dir, language='en', report_font=None):
    """Create both PDFs from one saved result; preserve existing outputs on failure."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    names = ('report_summary.pdf', 'report_detailed.pdf')
    if any((output_dir / name).exists() for name in names):
        raise FileExistsError('Preserve existing reports; choose a fresh output directory')
    with tempfile.TemporaryDirectory(prefix='audit-render-') as scratch:
        scratch = Path(scratch)
        write_summary_report(result, scratch / names[0], language, report_font)
        write_pdf_report(result, scratch / names[1], language, report_font)
        for name in names:
            with (output_dir / name).open('xb') as stream:
                stream.write((scratch / name).read_bytes())
    return tuple(output_dir / name for name in names)
