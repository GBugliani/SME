import io
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from django.utils import timezone

NAVY = colors.HexColor('#252525')
BLUE = colors.HexColor('#4169a9')
INK = colors.HexColor('#252525')
MUTED = colors.HexColor('#666666')
LINE = colors.HexColor('#dddddd')
AMBER = colors.HexColor('#b97922')


def number(value):
    if value is None:
        return 'Não disponível'
    return f'{value:,}'.replace(',', '.') if isinstance(value, int) else f'{value:.1f}'.replace('.', ',')


def date(value):
    if not value:
        return 'Não registrada'
    if isinstance(value, str):
        return '/'.join(value[:10].split('-')[::-1])
    if not isinstance(value, datetime):
        return value.strftime('%d/%m/%Y')
    return timezone.localtime(value).strftime('%d/%m/%Y, %H:%M')


def build_report(data):
    fonts = Path(reportlab.__file__).parent / 'fonts'
    if 'SME' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('SME', str(fonts / 'Vera.ttf')))
        pdfmetrics.registerFont(TTFont('SME-Bold', str(fonts / 'VeraBd.ttf')))
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, pageCompression=1)
    pdf.setTitle(f'SME | {data["territorio"]["nome"]} | {data["agravo_nome"]}')
    pdf.setAuthor('SME - Monitoramento epidemiológico')
    width, height = A4
    left, right = 42, width - 42
    content_width = right - left
    now = timezone.localtime()
    spec = data['integracao'] or {}
    points = data['serie']
    period = f'{date(points[0]["data"])} a {date(points[-1]["data"])}' if points else 'Sem registros'
    page_number = 1

    def text(value, x, y, size=10, color=INK, bold=False):
        pdf.setFillColor(color)
        pdf.setFont('SME-Bold' if bold else 'SME', size)
        pdf.drawString(x, y, str(value))

    def paragraph(value, x, top, w=content_width, size=10, color=INK, bold=False):
        style = ParagraphStyle('sme', fontName='SME-Bold' if bold else 'SME', fontSize=size,
                               leading=size*1.5, textColor=color, splitLongWords=True)
        p = Paragraph(escape(str(value)).replace('\n', '<br/>'), style)
        _, h = p.wrap(w, height)
        p.drawOn(pdf, x, top-h)
        return top-h

    def footer():
        pdf.setStrokeColor(LINE); pdf.line(left, 40, right, 40)
        text('SME - Monitoramento epidemiológico', left, 25, 8, MUTED)
        pdf.setFont('SME', 8); pdf.setFillColor(MUTED)
        pdf.drawRightString(right, 25, f'{page_number:02d}')

    def next_page(title):
        nonlocal page_number
        footer(); pdf.showPage(); page_number += 1
        text('SME - Monitoramento epidemiológico', left, height-40, 9, INK, True)
        text(title, left, height-72, 16, INK, True)
        pdf.setStrokeColor(LINE); pdf.line(left, height-88, right, height-88)
        return height-110

    text('SME - Monitoramento epidemiológico', left, height-42, 10, INK, True)
    text(f'Emissão: {now:%d/%m/%Y, %H:%M} (Brasília)', left, height-58, 8, MUTED)
    pdf.setStrokeColor(LINE); pdf.line(left, height-72, right, height-72)
    y = paragraph(data['territorio']['nome'], left, height-94, size=19, color=INK, bold=True)
    y = paragraph(f'{data["agravo_nome"]} - {spec.get("publicador", "Origem não informada")}', left, y-7, size=10)
    territory_kind = 'Município' if data['territorio']['tipo']=='municipio' else 'Região imediata'
    y = paragraph(f'Período: {period}  |  {territory_kind}  |  IBGE {data["territorio"]["codigo"]}', left, y-8, size=9, color=MUTED)-24
    quality = data['qualidade']
    indicators = [(number(data['casos_total']), 'Casos no período'),
             (str(data['semanas_com_dados']), 'Semanas com dados'),
             (str(data['anomalias']), 'Semanas sinalizadas'),
             (f'{number(quality["completude_percentual"])}%' if quality['completude_percentual'] is not None else 'N/D', 'Completude')]
    column_width = content_width/4
    pdf.setStrokeColor(LINE); pdf.line(left,y,right,y)
    for index, (value, label) in enumerate(indicators):
        x = left + index*column_width
        font_size = 14
        while pdfmetrics.stringWidth(value, 'SME-Bold', font_size) > column_width-12 and font_size > 9:
            font_size -= 1
        text(label, x, y-17, 8, MUTED)
        text(value, x, y-38, font_size, INK, True)
    pdf.line(left,y-53,right,y-53)
    y -= 83
    text('Evolução semanal', left, y, 12, INK, True)
    text(spec.get('indicador_nome', 'Casos notificados'), left, y-18, 9, MUTED)
    chart_top, chart_bottom = y-40, y-280
    x0, x1 = left+34, right-8
    maximum = max([1]+[float(p['casos']) for p in points if p.get('casos') is not None])
    for tick in range(5):
        yp = chart_bottom+(chart_top-chart_bottom)*tick/4
        pdf.setStrokeColor(LINE); pdf.setLineWidth(.5); pdf.line(x0, yp, x1, yp)
        text(number(round(maximum*tick/4)), left, yp-3, 8, MUTED)
    def xp(index): return x0+(x1-x0)*index/max(1,len(points)-1)
    def yp(value): return chart_bottom+(chart_top-chart_bottom)*float(value)/maximum
    for field, color, dashed in [('casos', BLUE, False)]:
        pdf.setStrokeColor(color); pdf.setLineWidth(1.2 if dashed else 2)
        pdf.setDash(4,3) if dashed else pdf.setDash()
        path = pdf.beginPath(); previous = False
        for index, point in enumerate(points):
            value = point.get(field)
            if value is None:
                previous = False; continue
            path.lineTo(xp(index),yp(value)) if previous else path.moveTo(xp(index),yp(value))
            previous = True
        pdf.drawPath(path)
        pdf.setDash()
    for index, point in enumerate(points):
        if point.get('casos') is not None and (point.get('anomalia') or len(points)==1 or (index>0 and points[index-1].get('casos') is None) or (index<len(points)-1 and points[index+1].get('casos') is None)):
            pdf.setFillColor(AMBER if point.get('anomalia') else BLUE);pdf.circle(xp(index),yp(point['casos']),2.8,fill=1,stroke=0)
    for index in sorted({round(i*(len(points)-1)/4) for i in range(5)}) if points else []:
        pdf.setFillColor(MUTED);pdf.setFont('SME',7)
        pdf.drawCentredString(xp(index),chart_bottom-16,date(points[index]['data']))
    text('Linha azul: contagens  /  Pontos âmbar: semanas acima do limiar estatístico', left, chart_bottom-39, 8, MUTED)
    y = paragraph('Lacunas interrompem a linha. Ausência de dados não equivale a zero casos. O detalhamento apresenta os valores calculados nas semanas sinalizadas.', left, chart_bottom-52, size=9, color=MUTED)
    paragraph('Sinalização estatística requer investigação. Este relatório não confirma surto nem substitui avaliação epidemiológica.',left,y-16,size=9,color=INK)
    y = next_page('Informações da consulta')
    text('Atualidade e cobertura',left,y,11,INK,True);y-=15
    facts=[('Última semana na base',date(data['atualidade']['ultima_semana_base'])),
           ('Última consulta à fonte',date(data['atualidade']['ultima_consulta_em'])),
           ('Processamento da série',date(data['atualizado_em'])),
           ('Semanas completas',f'{quality["semanas_completas"]} de {quality["semanas_esperadas"]}'),
           ('Municípios com dados',f'{quality["municipios_com_dados"]} de {quality["municipios_previstos"]}'),
           ('Semanas avaliáveis pelo detector',str(quality['semanas_avaliaveis']))]
    for label,value in facts:
        pdf.setStrokeColor(LINE);pdf.line(left,y-29,right,y-29)
        text(label,left,y-18,9,MUTED);text(value,left+285,y-18,9,INK,True);y-=34
    y-=24
    text('Método de detecção',left,y,11,INK,True);y-=15
    detector=data['detector']
    y=paragraph(f'{detector["nome"]} / versão {detector["versao"]}. Parâmetros: '+', '.join(f'{k}={v}' for k,v in detector['parametros'].items()),left,y,size=10)-12
    y=paragraph('A análise usa as revisões disponíveis na emissão. Novas publicações e reprocessamentos podem alterar contagens e sinalizações. O relatório preserva os valores desta emissão; o link de consulta mostra os dados atuais.',left,y,size=9,color=MUTED)-24
    text('Semanas sinalizadas no período',left,y,11,INK,True);y-=20
    flagged = [point for point in points if point.get('anomalia')]
    if not flagged:
        y=paragraph('Nenhuma semana sinalizada neste recorte. Isso não comprova ausência de surto ou de problemas de notificação.',left,y,size=9,color=MUTED)-20
    for point in flagged:
        from .alert_presentation import decimal_pt
        if y<135:y=next_page('Sinalizações / continuação')
        y=paragraph(f'{date(point["data"])} | Observado: {point["casos"]} | Referência: {decimal_pt(point["referencia"])} | Limiar: {decimal_pt(point["limiar"])}',left,y,size=9)-10
    if y<140:y=next_page('Fontes e lotes utilizados')
    text('Fontes e lotes utilizados',left,y,11,INK,True);y-=20
    for source in data['fontes']:
        lines=[source['nome'],source['url']]
        for lot in source.get('lotes',[]):
            lines.append(f'Lote {lot["id"]} | coletado em {date(lot["coletado_em"])} | SHA-256 {lot["sha256"]}')
        for index,line in enumerate(lines):
            required = Paragraph(escape(str(line)), ParagraphStyle('measure',fontName='SME-Bold' if index==0 else 'SME',fontSize=9,leading=13.5)).wrap(content_width,height)[1]
            if y-required<70:y=next_page('Fontes e lotes / continuação')
            y=paragraph(line,left,y,size=9,color=INK if index==0 else MUTED,bold=index==0)-5
        y-=14
    if data['territorio']['tipo']=='regiao':
        if y<130:y=next_page('Notas de cobertura')
        y=paragraph('Recorte regional: a cobertura é informada separadamente. Contagens com cobertura parcial não representam necessariamente todos os municípios da região.',left,y,size=10,color=MUTED)
    footer();pdf.save()
    return output.getvalue()
