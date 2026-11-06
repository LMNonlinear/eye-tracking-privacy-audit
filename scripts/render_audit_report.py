"""Render an audit result as a readable PDF without recalculating statistics."""
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle


TEXT = {
    'en': {
        'title': 'Group Privacy Audit Report', 'summary': 'Analysis overview',
        'scope': 'User-supplied plan note (not a method specification)', 'groups': 'Ordered group comparison',
        'baseline': 'Baseline', 'method': 'Method', 'calibration': 'Calibration status',
        'enabled': 'Formal decisions enabled', 'yes': 'Yes', 'no': 'No',
        'family': 'Family sizes (mechanism / residual and change / utility)', 'scores': 'Input score SHA-256',
        'condition': 'Condition summaries', 'datasets': 'Dataset', 'evaluator': 'Evaluator',
        'setting': 'Condition / comparison', 'overall': 'Overall %', 'group_a': 'Group A %',
        'group_b': 'Group B %', 'gap': 'A - B (pp)', 'effect': 'Effect (pp)',
        'interval': 'Pointwise 95% CI', 'p': 'Raw p', 'holm': 'Holm p',
        'decision': 'Decision', 'pass': 'Passed', 'not_pass': 'Not passed',
        'withheld': 'Withheld', 'na': 'Not estimable',
        'primary': 'Mechanism comparisons', 'secondary': 'Residual and baseline-change comparisons',
        'utility': 'Utility comparisons', 'none': 'No comparisons in this family.',
        'residual_rank1': 'Residual gap', 'change_from_baseline': 'Gap change from baseline',
        'diagnostics': 'Diagnostic annotations', 'chance': 'Chance %',
        'near': 'Near chance', 'folds': 'Fold differences (pp)',
        'interpretation': 'Interpretation and scope',
        'pointwise': 'Intervals are pointwise and conditional on the fitted models and observed galleries; they are not simultaneous confidence intervals.',
        'nonestimable': 'A nonestimable test is retained in its Holm family using p = 1 for multiplicity; its individual p-value and formal decision are withheld.',
        'near_note': 'Near-chance flags are descriptive and do not veto a residual-risk result. The chance reference uses the number of scored participants per fold and requires that this match the actual enrollment gallery.',
        'group_note': 'A and B follow the ordered group pair in the supplied plan. Positive gaps mean that A has a higher identification rate than B.',
        'change_note': 'Gap change equals the protected A - B gap minus the baseline gap. A negative change does not by itself establish equal group risk.',
        'nondetection_note': 'A comparison that does not pass correction does not establish that the two groups have equal risk.',
        'mechanism_note': 'For a declared pair, mechanism comparisons are the first condition gap minus the second; utility comparisons are the paired first-condition utility minus the second.',
        'method_note': 'The method named above governs this report. Plan fields for bootstrap, permutation and random seed are required by the legacy input schema but are not used by this t-based method.',
        'counts': 'Results: {passed} passed, {not_passed} did not pass, {withheld} withheld; {total} total.',
        'provenance': 'Provenance and limitations', 'unknown': 'Not specified',
        'page': 'Page', 'synthetic': 'Synthetic example: these values are not study results.',
    },
    'zh': {
        'title': '群体隐私保护审计报告', 'summary': '分析概况',
        'scope': '用户提供的计划备注（不作为统计方法说明）', 'groups': '群体比较顺序', 'baseline': '基线条件',
        'method': '统计方法', 'calibration': '校准状态', 'enabled': '是否允许正式判决',
        'yes': '是', 'no': '否', 'family': '比较族项目数（机制／剩余与变化／效用）', 'scores': '输入评分 SHA-256',
        'condition': '各条件识别率概况', 'datasets': '数据集', 'evaluator': '评估器',
        'setting': '条件／比较', 'overall': '总体 %', 'group_a': 'A组 %',
        'group_b': 'B组 %', 'gap': 'A－B（百分点）', 'effect': '差值（百分点）',
        'interval': '逐项95%区间', 'p': '原始p值', 'holm': '校正后p值',
        'decision': '判决', 'pass': '通过', 'not_pass': '未通过',
        'withheld': '暂不判决', 'na': '不可估计',
        'primary': '机制比较', 'secondary': '剩余差距与基线变化比较',
        'utility': '任务效用比较', 'none': '本比较族没有项目。',
        'residual_rank1': '剩余差距', 'change_from_baseline': '相对基线的差距变化',
        'diagnostics': '诊断提示', 'chance': '随机参考 %',
        'near': '接近随机参考', 'folds': '各折差距（百分点）',
        'interpretation': '结果解释与范围',
        'pointwise': '区间为以已训练模型和观察到的图库为条件的逐项区间，并非同时置信区间。',
        'nonestimable': '不可估计的检验仍保留在 Holm 比较族中，并以 p = 1 计入校正；该项的原始 p 值和正式判决暂不提供。',
        'near_note': '接近随机参考仅是描述性提示，不用于否决剩余风险结果。随机参考按每折评分参与者数计算，需与实际身份图库规模一致。',
        'group_note': 'A、B 对应所提供计划中的群体顺序；差距为正表示 A 组识别率高于 B 组。',
        'change_note': '差距变化等于保护后 A－B 差距减去基线差距。负值本身不能证明两组风险相同。',
        'nondetection_note': '比较未通过校正不等于证明两组风险相同。',
        'mechanism_note': '对于计划中声明的一对条件，机制比较为前一条件的群体差距减去后一条件的差距；效用比较为前一条件减后一条件的配对效用差。',
        'method_note': '本报告采用上方列出的统计方法。重采样次数、置换次数和随机种子为旧版输入格式要求，不控制当前的 t 方法。',
        'counts': '结果：通过 {passed} 项，未通过 {not_passed} 项，暂不判决 {withheld} 项；共 {total} 项。',
        'provenance': '来源与适用范围', 'unknown': '未提供',
        'page': '页', 'synthetic': '合成示例：以下数值不是研究实验结果。',
        'calibration_passed': '已通过所测条件下的评分层校准',
        'calibration_missing': '缺少独立校准记录',
        'calibration_failed': '校准未通过或统计源码发生变化',
    },
}

ZH_LIMITS = {
    'Score-level calibration does not establish independence in shared-gallery or overlapping-training data.': '评分层校准不能证明共享图库或重叠训练数据中参与者之间相互独立。',
    'Legacy six-check mode is a separate historical reproduction; diagnostic flags never veto residual-risk reporting.': '历史六检属于单独的复现路径；诊断提示不否决剩余风险的报告。',
    'No equivalence, causal ethnicity, deployment or strongest-attack guarantee.': '本流程不证明群体等效或族裔因果效应，也不提供部署或最强攻击保证。',
}

SYNTHETIC_SCOPE = 'Synthetic interface example only. Five equal-weight folds; approximate Welch-Satterthwaite t inference; residual and baseline-change tests in a separate Holm family. No personalization or deployment recommendation.'


def _number(value):
    if value is None:
        return '-'
    value = float(value)
    if value != 0 and abs(value) < 0.001:
        return f'{value:.3g}'
    return f'{value:.4f}'


def _font(report_font, language):
    """Use an embedded font; fail visibly if needed glyphs are unavailable."""
    candidates = [report_font] if report_font else []
    if not report_font and language == 'zh':
        candidates += [
            'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simsun.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
            '/usr/share/fonts/truetype/arphic/uming.ttc',
            '/System/Library/Fonts/PingFang.ttc',
        ]
    if not report_font and language == 'en':
        candidates.append(str(Path(reportlab.__file__).resolve().parent / 'fonts/Vera.ttf'))
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            font = TTFont('AuditReportFont', str(candidate), subfontIndex=0)
            pdfmetrics.registerFont(font)
            return font
        except Exception:
            if report_font:
                raise ValueError(f'Cannot load the supplied TrueType font: {candidate}') from None
    raise ValueError('No suitable TrueType font found. Supply --report-font with a Unicode TTF/TTC font path.')


def write_pdf_report(result, destination, language='en', report_font=None):
    """Write a paginated PDF from the saved result structure, preserving decisions."""
    if language not in TEXT:
        raise ValueError('Report language must be en or zh')
    t = TEXT[language]
    font = _font(report_font, language)
    styles = {
        'title': ParagraphStyle('title', fontName=font.fontName, fontSize=18, leading=23, textColor=colors.HexColor('#253846'), spaceAfter=12),
        'heading': ParagraphStyle('heading', fontName=font.fontName, fontSize=12, leading=16, textColor=colors.HexColor('#205f60'), spaceBefore=12, spaceAfter=6, keepWithNext=True),
        'body': ParagraphStyle('body', fontName=font.fontName, fontSize=9.3, leading=14, spaceAfter=5, wordWrap='CJK'),
        'cell': ParagraphStyle('cell', fontName=font.fontName, fontSize=7.5, leading=10.5, wordWrap='CJK' if language == 'zh' else None),
        'headcell': ParagraphStyle('headcell', fontName=font.fontName, fontSize=7.5, leading=10.5, textColor=colors.white, wordWrap='CJK' if language == 'zh' else None),
    }
    story = []

    def para(value, style='body'):
        value = str(value)
        missing = sorted({ch for ch in value if ord(ch) >= 32 and ord(ch) not in font.face.charWidths})
        if missing:
            raise ValueError('The selected PDF font lacks characters: ' + ''.join(missing[:12]) + '. Supply --report-font with a suitable Unicode TTF/TTC font.')
        return Paragraph(escape(value).replace('\n', '<br/>'), styles[style])

    def heading(label):
        story.append(para(label, 'heading'))

    def table(headers, rows, widths):
        data = [[para(x, 'headcell') for x in headers]]
        data += [[para(x, 'cell') for x in row] for row in rows]
        available = A4[0] - 40 * mm
        if sum(widths) > available:
            widths = [width * available / sum(widths) for width in widths]
        chart = LongTable(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        chart.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#276b6b')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f6f5')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LINEBELOW', (0, 0), (-1, 0), .5, colors.HexColor('#276b6b')),
        ]))
        story.append(chart)
        story.append(Spacer(1, 4 * mm))

    story.append(para(t['title'], 'title'))
    plan = result['plan']
    if 'synthetic' in str(plan.get('scope', '')).lower():
        story.append(para(t['synthetic']))
    heading(t['summary'])
    pair = plan['hypotheses'][0]
    calibration = result['calibration_status']
    if language == 'zh':
        calibration = {'independent_score_level_gates_passed': t['calibration_passed'],
                       'independent_calibration_missing': t['calibration_missing'],
                       'calibration_failed_or_method_changed': t['calibration_failed']}.get(calibration, calibration)
    for label, value in [
        (t['groups'], f'{pair[0]} - {pair[1]}'), (t['baseline'], plan['baseline']),
        (t['method'], result['analysis_mode']), (t['calibration'], calibration),
        (t['enabled'], t['yes'] if result['formal_decisions_enabled'] else t['no']),
        (t['family'], ' / '.join(map(str, result['family_sizes']))),
    ]:
        story.append(para(f'{label}: {value}'))
    story.append(para(t['group_note']))

    heading(t['condition'])
    rows = [[x['dataset'], x['evaluator'], x['condition'], _number(x['overall_rank1_percent']),
             _number(x['group_a_percent']), _number(x['group_b_percent']), _number(x['signed_gap_pp'])]
            for x in result['condition_results']]
    table([t['datasets'], t['evaluator'], t['setting'], t['overall'], t['group_a'], t['group_b'], t['gap']], rows,
          [65, 65, 100, 56, 56, 56, 55])

    for key, label in [('primary_tests', 'primary'), ('secondary_tests', 'secondary'), ('utility_tests', 'utility')]:
        heading(t[label])
        comparisons = result[key]
        if not comparisons:
            story.append(para(t['none']))
            continue
        passed = sum(x.get('passes_correction') is True for x in comparisons)
        not_passed = sum(x.get('passes_correction') is False for x in comparisons)
        withheld = sum(x.get('passes_correction') is None for x in comparisons)
        story.append(para(t['counts'].format(passed=passed, not_passed=not_passed, withheld=withheld, total=len(comparisons))))
        rows = []
        for x in comparisons:
            comparison = x.get('condition')
            if comparison is not None:
                comparison += '\n' + t.get(x.get('endpoint', ''), x.get('endpoint', ''))
            else:
                comparison = str(x.get('left', '')) + ' - ' + str(x.get('right', ''))
            ci = x.get('ci95')
            interval = '[' + _number(ci[0]) + ', ' + _number(ci[1]) + ']' if ci is not None else '-'
            decision = t['withheld'] if x.get('passes_correction') is None else t['pass'] if x['passes_correction'] else t['not_pass']
            rows.append([x['dataset'], x.get('evaluator', '-'), comparison, _number(x['diff_pp']), interval,
                         _number(x.get('p')), _number(x.get('holm_p')), decision])
        table([t['datasets'], t['evaluator'], t['setting'], t['effect'], t['interval'], t['p'], t['holm'], t['decision']],
              rows, [53, 53, 96, 55, 91, 55, 55, 49])

    heading(t['diagnostics'])
    rows = [[x['dataset'], x['evaluator'], x['condition'], _number(x['full_gallery_chance_percent']),
             t['yes'] if x['near_chance_descriptive'] else t['no'], ', '.join(_number(v) for v in x['fold_differences_pp'])]
            for x in result['diagnostic_annotations']]
    table([t['datasets'], t['evaluator'], t['setting'], t['chance'], t['near'], t['folds']], rows,
          [55, 55, 90, 58, 80, 164])
    heading(t['interpretation'])
    for key in ('pointwise', 'nonestimable', 'near_note', 'change_note', 'nondetection_note', 'mechanism_note', 'method_note'):
        story.append(para(t[key]))
    heading(t['provenance'])
    story.append(para(f"{t['scores']}: {result['scores_sha256']}"))
    # Preserve the input plan's own description without turning it into a claim.
    scope = plan.get('scope', t['unknown'])
    if language == 'zh' and scope == SYNTHETIC_SCOPE:
        scope = '仅用于合成接口示例。五折等权；采用 Welch-Satterthwaite 近似 t 推断；剩余差距和基线差距变化构成单独的 Holm 比较族。不提供个性化或部署建议。'
    story.append(para(f"{t['scope']}: {scope}"))
    for limit in result.get('limits', []):
        story.append(para(ZH_LIMITS.get(limit, limit) if language == 'zh' else limit))

    def footer(canvas, doc):
        canvas.setFont(font.fontName, 8)
        canvas.setFillColor(colors.HexColor('#647681'))
        canvas.drawRightString(A4[0] - 20 * mm, 13 * mm, f"{t['page']} {doc.page}")

    doc = SimpleDocTemplate(str(destination), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=20 * mm,
                            title=t['title'], author='Group Privacy Audit')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main():
    """Render a pre-existing report without re-running or changing its analysis."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Render an existing audit JSON as a PDF report')
    parser.add_argument('--input', required=True, help='Existing report.json')
    parser.add_argument('--output', required=True, help='New PDF file; existing files are not overwritten')
    parser.add_argument('--report-language', choices=['en', 'zh'], default='en')
    parser.add_argument('--report-font', help='Unicode TrueType font (.ttf/.ttc)')
    args = parser.parse_args()
    destination = Path(args.output)
    if destination.exists():
        raise FileExistsError('Preserve existing reports; choose a fresh PDF path')
    result = json.loads(Path(args.input).read_text(encoding='utf8'))
    write_pdf_report(result, destination, args.report_language, args.report_font)
    print(f'REPORT_COMPLETE {destination}', flush=True)


if __name__ == '__main__':
    main()
