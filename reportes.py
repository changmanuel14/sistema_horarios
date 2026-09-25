from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from io import BytesIO
from models import (db, Carrera, Seccion, Curso, Docente, Ciclo, BloqueHorario, Asignacion, RestriccionDocente, CicloCarrera)
import os
from openpyxl.drawing.image import Image as XLImage

DIAS_NOMBRE = {1: 'Lunes', 2: 'Martes', 3: 'Miércoles', 
               4: 'Jueves', 5: 'Viernes', 6: 'Sábado', 7: 'Domingo'}
DIAS_CORTO = {1: 'Lun', 2: 'Mar', 3: 'Mié', 4: 'Jue', 5: 'Vie', 6: 'Sáb', 7: 'Dom'}

MODALIDAD_NOMBRE = {
    'presencial': 'Presencial',
    'virtual': 'Virtual',
    'laboratorio_escuela': 'Lab. Escuela',
    'laboratorio_radiologia': 'Lab. Radiología'
}

MODALIDAD_COLOR = {
    'presencial': '#D4EDDA',
    'virtual': '#E2D6F7',
    'laboratorio_escuela': '#FFE5B4',
    'laboratorio_radiologia': '#FADBD8'
}

# Ruta absoluta a la carpeta de logos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGOS_DIR = os.path.join(BASE_DIR, 'static', 'logos')
LOGO_GALILEO = os.path.join(LOGOS_DIR, 'logo_galileo.png')
LOGO_FACISA = os.path.join(LOGOS_DIR, 'logo_facisa.png')


# ============================================================
# Funciones auxiliares
# ============================================================
def insertar_logos_excel(ws):
    """Inserta los dos logos en la parte superior de la hoja de Excel."""
    if not os.path.exists(LOGO_GALILEO) or not os.path.exists(LOGO_FACISA):
        return
    
    # Insertar logo izquierdo (Galileo) en A1
    logo_izq = XLImage(LOGO_GALILEO)
    logo_izq.width = 225
    logo_izq.height = 75
    ws.add_image(logo_izq, 'A1')
    
    # Insertar logo derecho (FACISA) en H1
    logo_der = XLImage(LOGO_FACISA)
    logo_der.width = 225
    logo_der.height = 75
    ws.add_image(logo_der, 'H1')
    
    # Ajustar altura de las primeras filas para dar espacio a los logos
    ws.row_dimensions[1].height = 60
    
def construir_encabezado_logos():
    """Construye una tabla con los dos logos (izquierda y derecha) para usar en PDFs."""
    from reportlab.platypus import Image as RLImage
    from reportlab.lib.units import inch
    
    # Verificar que existan los logos
    logo_izq = RLImage(LOGO_GALILEO, width=2.8*inch, height=0.9*inch) if os.path.exists(LOGO_GALILEO) else ''
    logo_der = RLImage(LOGO_FACISA, width=2.8*inch, height=0.9*inch) if os.path.exists(LOGO_FACISA) else ''
    
    tabla_logos = Table([[logo_izq, logo_der]], colWidths=[4*inch, 4*inch])
    tabla_logos.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return tabla_logos

def obtener_datos_horario_seccion(ciclo_id, seccion_id):
    """Obtiene las asignaciones de una sección con toda la info necesaria."""
    asignaciones = Asignacion.query.filter_by(
        id_ciclo=ciclo_id, id_seccion=seccion_id
    ).all()
    
    bloques = BloqueHorario.query.filter_by(id_seccion=seccion_id).all()
    
    return {
        'asignaciones': asignaciones,
        'bloques': bloques
    }


def construir_grilla(bloques, asignaciones):
    """Construye una matriz (hora, día) con las asignaciones."""
    # Horas únicas ordenadas
    horas = sorted(set(b.hora_inicio for b in bloques))
    
    grilla = {}
    for h in horas:
        grilla[h] = {d: None for d in range(1, 8)}
    
    for a in asignaciones:
        b = a.bloque
        grilla[b.hora_inicio][b.dia] = {
            'curso': a.curso.nombre,
            'docente': a.docente.nombre_completo if a.docente else '—',
            'modalidad': a.modalidad,
            'hora_fin': b.hora_fin.strftime('%H:%M')
        }
    
    return grilla, horas


# ============================================================
# PDF: Horario de una sección
# ============================================================
def generar_pdf_seccion(ciclo, seccion, carrera):
    """Genera PDF del horario de una sección."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        'Titulo', parent=styles['Heading1'],
        fontSize=16, alignment=1, spaceAfter=10
    )
    subtitulo_style = ParagraphStyle(
        'Subtitulo', parent=styles['Heading2'],
        fontSize=12, alignment=1, spaceAfter=15
    )
    
    datos = obtener_datos_horario_seccion(ciclo.id, seccion.id)
    grilla, horas = construir_grilla(datos['bloques'], datos['asignaciones'])
    
    elementos = []
    # ← AGREGAR LOGOS AL INICIO
    elementos.append(construir_encabezado_logos())
    elementos.append(Spacer(1, 10))
    
    elementos.append(Paragraph(f"Horario - {ciclo.nombre}", titulo_style))
    elementos.append(Paragraph(
        f"{carrera.nombre} | Semestre {seccion.semestre} | Sección {seccion.nombre}",
        subtitulo_style
    ))
    
    # Construir tabla
    header = ['Hora'] + [DIAS_CORTO[d] for d in range(1, 8)]
    tabla_data = [header]
    
    for h in horas:
        fila = [f"{h.strftime('%H:%M')} - {grilla[h][1]['hora_fin'] if grilla[h][1] else ''}"]
        # Buscar la hora_fin de algún bloque de esa hora
        bloque_ref = next((b for b in datos['bloques'] if b.hora_inicio == h and b.tipo == 'clase'), None)
        if bloque_ref:
            fila[0] = f"{h.strftime('%H:%M')} - {bloque_ref.hora_fin.strftime('%H:%M')}"
        else:
            bloque_ref = next((b for b in datos['bloques'] if b.hora_inicio == h), None)
            if bloque_ref:
                fila[0] = f"{h.strftime('%H:%M')} - {bloque_ref.hora_fin.strftime('%H:%M')}"
        
        for d in range(1, 8):
            celda = grilla[h].get(d)
            if celda:
                texto = f"<b>{celda['curso']}</b><br/>{celda['docente']}<br/><i>{MODALIDAD_NOMBRE.get(celda['modalidad'], celda['modalidad'])}</i>"
                fila.append(Paragraph(texto, styles['Normal']))
            else:
                fila.append('')
        tabla_data.append(fila)
    
    tabla = Table(tabla_data, colWidths=[1.2*inch] + [1.3*inch]*7)
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#ECF0F1')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ])
    
    # Colorear celdas según modalidad
    for i, h in enumerate(horas, start=1):
        for d in range(1, 8):
            celda = grilla[h].get(d)
            if celda:
                color = MODALIDAD_COLOR.get(celda['modalidad'], '#FFFFFF')
                style.add('BACKGROUND', (d, i), (d, i), colors.HexColor(color))
    
    tabla.setStyle(style)
    elementos.append(tabla)
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer


# ============================================================
# PDF: Horario de un laboratorio
# ============================================================
def generar_pdf_laboratorio(ciclo, modalidad_lab):
    """Genera PDF del horario de un laboratorio específico."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'],
                                   fontSize=16, alignment=1, spaceAfter=10)
    subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Heading2'],
                                      fontSize=12, alignment=1, spaceAfter=15)
    
    nombre_lab = MODALIDAD_NOMBRE.get(modalidad_lab, modalidad_lab)
    
    # Obtener todas las asignaciones de este laboratorio en el ciclo
    asignaciones = Asignacion.query.filter_by(
        id_ciclo=ciclo.id, modalidad=modalidad_lab
    ).all()
    
    elementos = []
    # ← AGREGAR LOGOS AL INICIO
    elementos.append(construir_encabezado_logos())
    elementos.append(Spacer(1, 10))
    
    elementos.append(Paragraph(f"Horario {nombre_lab} - {ciclo.nombre}", titulo_style))
    elementos.append(Paragraph(
        f"Vista consolidada de todas las secciones",
        subtitulo_style
    ))
    
    if not asignaciones:
        elementos.append(Paragraph("No hay asignaciones registradas en este laboratorio.", styles['Normal']))
        doc.build(elementos)
        buffer.seek(0)
        return buffer
    
    # Obtener horas únicas de todos los bloques involucrados
    bloques_ids = [a.id_bloque for a in asignaciones]
    bloques = BloqueHorario.query.filter(BloqueHorario.id.in_(bloques_ids)).all()
    horas = sorted(set(b.hora_inicio for b in bloques))
    
    # Construir grilla: hora -> dia -> lista de asignaciones
    grilla = {}
    for h in horas:
        grilla[h] = {d: [] for d in range(1, 8)}
    
    for a in asignaciones:
        b = a.bloque
        sec = a.seccion
        car = sec.semestre  # Obtener carrera a través de la sección
        # Necesitamos la carrera
        from models import Carrera as CarreraModel
        # La sección tiene id_carrera, pero en nuestro modelo simplificado no lo tiene
        # Vamos a obtenerlo a través del curso
        carrera = a.curso.id_carrera
        carrera_obj = CarreraModel.query.get(carrera)
        
        grilla[b.hora_inicio][b.dia].append({
            'curso': a.curso.nombre,
            'docente': a.docente.nombre_completo if a.docente else '—',
            'seccion': f"Sem {sec.semestre}-{sec.nombre}",
            'carrera': carrera_obj.nombre if carrera_obj else ''
        })
    
    # Construir tabla
    header = ['Hora'] + [DIAS_CORTO[d] for d in range(1, 8)]
    tabla_data = [header]
    
    for h in horas:
        bloque_ref = next((b for b in bloques if b.hora_inicio == h), None)
        fila = [f"{h.strftime('%H:%M')} - {bloque_ref.hora_fin.strftime('%H:%M')}" if bloque_ref else h.strftime('%H:%M')]
        
        for d in range(1, 8):
            items = grilla[h].get(d, [])
            if items:
                texto = '<br/>'.join([
                    f"<b>{it['curso']}</b><br/>{it['carrera']} {it['seccion']}<br/>{it['docente']}"
                    for it in items
                ])
                fila.append(Paragraph(texto, styles['Normal']))
            else:
                fila.append('')
        tabla_data.append(fila)
    
    tabla = Table(tabla_data, colWidths=[1.2*inch] + [1.3*inch]*7)
    color_lab = MODALIDAD_COLOR.get(modalidad_lab, '#FFFFFF')
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#ECF0F1')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
    ])
    
    # Colorear celdas ocupadas
    for i, h in enumerate(horas, start=1):
        for d in range(1, 8):
            if grilla[h].get(d):
                style.add('BACKGROUND', (d, i), (d, i), colors.HexColor(color_lab))
    
    tabla.setStyle(style)
    elementos.append(tabla)
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer


# ============================================================
# PDF: Todas las secciones del ciclo (vitrina)
# ============================================================
def generar_pdf_todas_secciones(ciclo):
    """Genera PDF con todas las secciones del ciclo, agrupadas por carrera/semestre/sección."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'],
                                   fontSize=18, alignment=1, spaceAfter=15)
    subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Heading2'],
                                      fontSize=12, alignment=1, spaceAfter=15)
    
    elementos = []
    
    # ← AGREGAR LOGOS AL INICIO
    elementos.append(construir_encabezado_logos())
    elementos.append(Spacer(1, 10))
    
    elementos.append(Paragraph(f"Horarios Generales - {ciclo.nombre}", titulo_style))
    elementos.append(Paragraph(
        f"Del {ciclo.fecha_inicio.strftime('%d/%m/%Y')} al {ciclo.fecha_fin.strftime('%d/%m/%Y')}",
        subtitulo_style
    ))
    elementos.append(Spacer(1, 20))
    
    # Obtener todas las secciones activas en el ciclo
    from models import CicloCarrera
    # En nuestro modelo simplificado, Seccion tiene id_carrera
    carreras_activas = db.session.query(Carrera).join(
        CicloCarrera, Carrera.id == CicloCarrera.id_carrera
    ).filter(CicloCarrera.id_ciclo == ciclo.id).order_by(Carrera.nombre).all()
    
    primera_pagina = True
    for carrera in carreras_activas:
        secciones = Seccion.query.filter_by(id_carrera=carrera.id).order_by(
            Seccion.semestre, Seccion.nombre
        ).all()
        
        if not secciones:
            continue
        
        for seccion in secciones:
            if not primera_pagina:
                elementos.append(PageBreak())
            primera_pagina = False
            
            datos = obtener_datos_horario_seccion(ciclo.id, seccion.id)
            if not datos['asignaciones'] and not datos['bloques']:
                continue
            
            grilla, horas = construir_grilla(datos['bloques'], datos['asignaciones'])
            
            # Encabezado de sección
            sec_style = ParagraphStyle('Sec', parent=styles['Heading2'],
                                        fontSize=14, textColor=colors.HexColor('#2C3E50'),
                                        spaceAfter=10)
            elementos.append(Paragraph(
                f"{carrera.nombre} - Semestre {seccion.semestre} - Sección {seccion.nombre}",
                sec_style
            ))
            
            # Tabla
            header = ['Hora'] + [DIAS_CORTO[d] for d in range(1, 8)]
            tabla_data = [header]
            
            for h in horas:
                bloque_ref = next((b for b in datos['bloques'] if b.hora_inicio == h), None)
                fila = [f"{h.strftime('%H:%M')}-{bloque_ref.hora_fin.strftime('%H:%M')}" if bloque_ref else h.strftime('%H:%M')]
                
                for d in range(1, 8):
                    celda = grilla[h].get(d)
                    if celda:
                        texto = f"<b>{celda['curso']}</b><br/>{celda['docente']}<br/><i>{MODALIDAD_NOMBRE.get(celda['modalidad'], celda['modalidad'])}</i>"
                        fila.append(Paragraph(texto, styles['Normal']))
                    else:
                        fila.append('')
                tabla_data.append(fila)
            
            tabla = Table(tabla_data, colWidths=[1.1*inch] + [1.3*inch]*7)
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#ECF0F1')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
            ])
            
            for i, h in enumerate(horas, start=1):
                for d in range(1, 8):
                    celda = grilla[h].get(d)
                    if celda:
                        color = MODALIDAD_COLOR.get(celda['modalidad'], '#FFFFFF')
                        style.add('BACKGROUND', (d, i), (d, i), colors.HexColor(color))
            
            tabla.setStyle(style)
            elementos.append(tabla)
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer


# ============================================================
# Excel: Todas las secciones del ciclo (lista administrativa)
# ============================================================
def generar_excel_todas_secciones(ciclo):
    """Genera Excel con todas las secciones del ciclo en formato lista."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Horarios"
    
    #Insertar Logos
    insertar_logos_excel(ws)
    # Estilos
    header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Encabezado
    ws.merge_cells('A3:I3')
    ws['A3'] = f"Horarios del Ciclo: {ciclo.nombre}"
    ws['A3'].font = Font(size=14, bold=True)
    ws['A3'].alignment = Alignment(horizontal='center')
    
    ws.merge_cells('A4:I4')
    ws['A4'] = f"Del {ciclo.fecha_inicio.strftime('%d/%m/%Y')} al {ciclo.fecha_fin.strftime('%d/%m/%Y')}"
    ws['A4'].alignment = Alignment(horizontal='center')
    
    # Encabezados de columna
    headers = ['Carrera', 'Semestre', 'Sección', 'Día', 'Hora Inicio', 'Hora Fin',
               'Curso', 'Docente', 'Modalidad']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=6, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal='center')
    
    # Datos
    row = 7
    from models import CicloCarrera
    carreras_activas = db.session.query(Carrera).join(
        CicloCarrera, Carrera.id == CicloCarrera.id_carrera
    ).filter(CicloCarrera.id_ciclo == ciclo.id).order_by(Carrera.nombre).all()
    
    for carrera in carreras_activas:
        secciones = Seccion.query.filter_by(id_carrera=carrera.id).order_by(
            Seccion.semestre, Seccion.nombre
        ).all()
        
        for seccion in secciones:
            asignaciones = Asignacion.query.filter_by(
                id_ciclo=ciclo.id, id_seccion=seccion.id
            ).all()
            
            # Ordenar por día y hora
            asignaciones_sorted = sorted(asignaciones, key=lambda a: (a.bloque.dia, a.bloque.hora_inicio))
            
            for a in asignaciones_sorted:
                ws.cell(row=row, column=1, value=carrera.nombre).border = border
                ws.cell(row=row, column=2, value=seccion.semestre).border = border
                ws.cell(row=row, column=3, value=seccion.nombre).border = border
                ws.cell(row=row, column=4, value=DIAS_NOMBRE[a.bloque.dia]).border = border
                ws.cell(row=row, column=5, value=a.bloque.hora_inicio.strftime('%H:%M')).border = border
                ws.cell(row=row, column=6, value=a.bloque.hora_fin.strftime('%H:%M')).border = border
                ws.cell(row=row, column=7, value=a.curso.nombre).border = border
                docente_nombre = a.docente.nombre_completo_invertido if a.docente else '—'
                ws.cell(row=row, column=8, value=docente_nombre).border = border
                ws.cell(row=row, column=9, value=MODALIDAD_NOMBRE.get(a.modalidad, a.modalidad)).border = border
                row += 1
    
    # Ajustar anchos de columna
    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 10
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 25
    ws.column_dimensions['H'].width = 25
    ws.column_dimensions['I'].width = 18
    
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ============================================================
# Excel: Horario de un laboratorio
# ============================================================
def generar_excel_laboratorio(ciclo, modalidad_lab):
    """Genera Excel del horario de un laboratorio específico."""
    wb = Workbook()
    ws = wb.active
    ws.title = MODALIDAD_NOMBRE.get(modalidad_lab, 'Laboratorio')
    
    # ← INSERTAR LOGOS
    insertar_logos_excel(ws)
    
    header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    nombre_lab = MODALIDAD_NOMBRE.get(modalidad_lab, modalidad_lab)
    
    ws.merge_cells('A3:H3')
    ws['A3'] = f"Horario {nombre_lab} - {ciclo.nombre}"
    ws['A3'].font = Font(size=14, bold=True)
    ws['A3'].alignment = Alignment(horizontal='center')
    
    headers = ['Carrera', 'Semestre', 'Sección', 'Día', 'Hora Inicio', 'Hora Fin',
               'Curso', 'Docente']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=5, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal='center')
    
    asignaciones = Asignacion.query.filter_by(
        id_ciclo=ciclo.id, modalidad=modalidad_lab
    ).all()
    
    row = 6
    # Ordenar por día, hora, carrera
    asignaciones_sorted = sorted(asignaciones, key=lambda a: (
        a.bloque.dia, a.bloque.hora_inicio, a.curso.id_carrera
    ))
    
    for a in asignaciones_sorted:
        sec = a.seccion
        carrera = Carrera.query.get(a.curso.id_carrera)
        
        ws.cell(row=row, column=1, value=carrera.nombre if carrera else '').border = border
        ws.cell(row=row, column=2, value=sec.semestre).border = border
        ws.cell(row=row, column=3, value=sec.nombre).border = border
        ws.cell(row=row, column=4, value=DIAS_NOMBRE[a.bloque.dia]).border = border
        ws.cell(row=row, column=5, value=a.bloque.hora_inicio.strftime('%H:%M')).border = border
        ws.cell(row=row, column=6, value=a.bloque.hora_fin.strftime('%H:%M')).border = border
        ws.cell(row=row, column=7, value=a.curso.nombre).border = border
        docente_nombre = a.docente.nombre_completo_invertido if a.docente else '—'
        ws.cell(row=row, column=8, value=docente_nombre).border = border
        row += 1
    
    # Ajustar anchos
    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 10
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 25
    ws.column_dimensions['H'].width = 25
    
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ============================================================
# PDF: Horario de un docente
# ============================================================
def generar_pdf_docente(ciclo, docente):
    """Genera PDF del horario de un docente específico."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'],
                                   fontSize=16, alignment=1, spaceAfter=10)
    subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Heading2'],
                                      fontSize=12, alignment=1, spaceAfter=15)
    
    elementos = []
    # ← AGREGAR LOGOS AL INICIO
    elementos.append(construir_encabezado_logos())
    elementos.append(Spacer(1, 10))
    
    elementos.append(Paragraph(f"Horario del Docente - {ciclo.nombre}", titulo_style))
    
    # ← CORREGIR ORDEN DEL NOMBRE
    elementos.append(Paragraph(docente.nombre_con_grado, subtitulo_style))
    
    if docente.correo:
        elementos.append(Paragraph(f"Correo: {docente.correo}", styles['Normal']))
    
    elementos.append(Spacer(1, 15))
    
    # Obtener todas las asignaciones del docente en el ciclo
    asignaciones = Asignacion.query.filter_by(
        id_ciclo=ciclo.id, id_docente=docente.id
    ).all()
    
    if not asignaciones:
        elementos.append(Paragraph("Este docente no tiene asignaciones en este ciclo.", styles['Normal']))
        doc.build(elementos)
        buffer.seek(0)
        return buffer
    
    # Obtener horas únicas
    bloques_ids = [a.id_bloque for a in asignaciones]
    bloques = BloqueHorario.query.filter(BloqueHorario.id.in_(bloques_ids)).all()
    horas = sorted(set(b.hora_inicio for b in bloques))
    
    # Construir grilla
    grilla = {}
    for h in horas:
        grilla[h] = {d: [] for d in range(1, 8)}
    
    for a in asignaciones:
        b = a.bloque
        sec = a.seccion
        carrera = Carrera.query.get(a.curso.id_carrera)
        grilla[b.hora_inicio][b.dia].append({
            'curso': a.curso.nombre,
            'carrera': carrera.nombre if carrera else '',
            'seccion': f"Sem {sec.semestre}-{sec.nombre}",
            'modalidad': a.modalidad
        })
    
    # Tabla
    header = ['Hora'] + [DIAS_CORTO[d] for d in range(1, 8)]
    tabla_data = [header]
    
    for h in horas:
        bloque_ref = next((b for b in bloques if b.hora_inicio == h), None)
        fila = [f"{h.strftime('%H:%M')}-{bloque_ref.hora_fin.strftime('%H:%M')}" if bloque_ref else h.strftime('%H:%M')]
        
        for d in range(1, 8):
            items = grilla[h].get(d, [])
            if items:
                texto = '<br/>'.join([
                    f"<b>{it['curso']}</b><br/>{it['carrera']} {it['seccion']}<br/><i>{MODALIDAD_NOMBRE.get(it['modalidad'], it['modalidad'])}</i>"
                    for it in items
                ])
                fila.append(Paragraph(texto, styles['Normal']))
            else:
                fila.append('')
        tabla_data.append(fila)
    
    tabla = Table(tabla_data, colWidths=[1.2*inch] + [1.3*inch]*7)
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#ECF0F1')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ])
    
    # Colorear celdas
    for i, h in enumerate(horas, start=1):
        for d in range(1, 8):
            items = grilla[h].get(d, [])
            if items:
                # Usar el color de la primera modalidad
                color = MODALIDAD_COLOR.get(items[0]['modalidad'], '#FFFFFF')
                style.add('BACKGROUND', (d, i), (d, i), colors.HexColor(color))
    
    tabla.setStyle(style)
    elementos.append(tabla)
    
    # Agregar restricciones del docente
    restricciones = RestriccionDocente.query.filter_by(id_docente=docente.id).order_by(
        RestriccionDocente.dia, RestriccionDocente.hora_inicio
    ).all()
    
    if restricciones:
        elementos.append(Spacer(1, 20))
        elementos.append(Paragraph("Restricciones de Horario:", styles['Heading3']))
        
        res_data = [['Día', 'Horario', 'Motivo']]
        for r in restricciones:
            res_data.append([
                DIAS_NOMBRE[r.dia],
                f"{r.hora_inicio.strftime('%H:%M')} - {r.hora_fin.strftime('%H:%M')}",
                r.motivo or '—'
            ])
        
        res_table = Table(res_data, colWidths=[2*inch, 2*inch, 4*inch])
        res_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E74C3C')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elementos.append(res_table)
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer


# ============================================================
# PDF: Horarios de todos los docentes
# ============================================================
def generar_pdf_todos_docentes(ciclo):
    """Genera PDF con el horario de cada docente del ciclo."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'],
                                   fontSize=18, alignment=1, spaceAfter=10)
    subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Heading2'],
                                      fontSize=12, alignment=1, spaceAfter=15)
    
    elementos = []
    # ← AGREGAR LOGOS AL INICIO (solo en la primera página)
    elementos.append(construir_encabezado_logos())
    elementos.append(Spacer(1, 10))
    
    elementos.append(Paragraph(f"Horarios de Docentes - {ciclo.nombre}", titulo_style))
    elementos.append(Paragraph(
        f"Del {ciclo.fecha_inicio.strftime('%d/%m/%Y')} al {ciclo.fecha_fin.strftime('%d/%m/%Y')}",
        subtitulo_style
    ))
    
    # Obtener docentes que tienen asignaciones en este ciclo
    docentes_ids = db.session.query(Asignacion.id_docente).filter(
        Asignacion.id_ciclo == ciclo.id,
        Asignacion.id_docente.isnot(None)
    ).distinct().all()
    docentes_ids = [d[0] for d in docentes_ids]
    
    docentes = Docente.query.filter(Docente.id.in_(docentes_ids)).order_by(
        Docente.apellidos, Docente.nombres
    ).all()
    
    primera_pagina = True
    for docente in docentes:
        if not primera_pagina:
            elementos.append(PageBreak())
        primera_pagina = False
        
        asignaciones = Asignacion.query.filter_by(
            id_ciclo=ciclo.id, id_docente=docente.id
        ).all()
        
        # Encabezado
        doc_style = ParagraphStyle('Doc', parent=styles['Heading2'],
                                    fontSize=14, textColor=colors.HexColor('#2C3E50'),
                                    spaceAfter=10)
        elementos.append(Paragraph(docente.nombre_con_grado, doc_style))
        
        if not asignaciones:
            elementos.append(Paragraph("Sin asignaciones en este ciclo.", styles['Normal']))
            continue
        
        # Obtener horas únicas
        bloques_ids = [a.id_bloque for a in asignaciones]
        bloques = BloqueHorario.query.filter(BloqueHorario.id.in_(bloques_ids)).all()
        horas = sorted(set(b.hora_inicio for b in bloques))
        
        # Construir grilla
        grilla = {}
        for h in horas:
            grilla[h] = {d: [] for d in range(1, 8)}
        
        for a in asignaciones:
            b = a.bloque
            sec = a.seccion
            carrera = Carrera.query.get(a.curso.id_carrera)
            grilla[b.hora_inicio][b.dia].append({
                'curso': a.curso.nombre,
                'carrera': carrera.nombre if carrera else '',
                'seccion': f"Sem {sec.semestre}-{sec.nombre}",
                'modalidad': a.modalidad
            })
        
        # Tabla
        header = ['Hora'] + [DIAS_CORTO[d] for d in range(1, 8)]
        tabla_data = [header]
        
        for h in horas:
            bloque_ref = next((b for b in bloques if b.hora_inicio == h), None)
            fila = [f"{h.strftime('%H:%M')}-{bloque_ref.hora_fin.strftime('%H:%M')}" if bloque_ref else h.strftime('%H:%M')]
            
            for d in range(1, 8):
                items = grilla[h].get(d, [])
                if items:
                    texto = '<br/>'.join([
                        f"<b>{it['curso']}</b><br/>{it['carrera']} {it['seccion']}<br/><i>{MODALIDAD_NOMBRE.get(it['modalidad'], it['modalidad'])}</i>"
                        for it in items
                    ])
                    fila.append(Paragraph(texto, styles['Normal']))
                else:
                    fila.append('')
            tabla_data.append(fila)
        
        tabla = Table(tabla_data, colWidths=[1.1*inch] + [1.3*inch]*7)
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#ECF0F1')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
        ])
        
        for i, h in enumerate(horas, start=1):
            for d in range(1, 8):
                items = grilla[h].get(d, [])
                if items:
                    color = MODALIDAD_COLOR.get(items[0]['modalidad'], '#FFFFFF')
                    style.add('BACKGROUND', (d, i), (d, i), colors.HexColor(color))
        
        tabla.setStyle(style)
        elementos.append(tabla)
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer

def generar_pdf_vitrina_presencial(ciclo):
    """Genera PDF de vitrina incluyendo SOLO secciones con al menos un periodo presencial."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'],
                                   fontSize=18, alignment=1, spaceAfter=15)
    subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Heading2'],
                                      fontSize=12, alignment=1, spaceAfter=15)
    
    elementos = []
    
    # ← AGREGAR LOGOS AL INICIO
    elementos.append(construir_encabezado_logos())
    elementos.append(Spacer(1, 10))
    
    elementos.append(Paragraph(f"Horarios Presenciales - {ciclo.nombre}", titulo_style))
    elementos.append(Paragraph(
        f"Del {ciclo.fecha_inicio.strftime('%d/%m/%Y')} al {ciclo.fecha_fin.strftime('%d/%m/%Y')}",
        subtitulo_style
    ))
    elementos.append(Spacer(1, 20))
    
    # Obtener carreras activas en el ciclo
    carreras_activas = db.session.query(Carrera).join(
        CicloCarrera, Carrera.id == CicloCarrera.id_carrera
    ).filter(CicloCarrera.id_ciclo == ciclo.id).order_by(Carrera.nombre).all()
    
    primera_pagina = True
    secciones_incluidas = 0
    
    for carrera in carreras_activas:
        secciones = Seccion.query.filter_by(id_carrera=carrera.id).order_by(
            Seccion.semestre, Seccion.nombre
        ).all()
        
        if not secciones:
            continue
        
        for seccion in secciones:
            # ← FILTRO CLAVE: Verificar si la sección tiene al menos un periodo presencial
            tiene_presencial = Asignacion.query.filter_by(
                id_ciclo=ciclo.id,
                id_seccion=seccion.id,
                modalidad='presencial'
            ).first() is not None
            
            # Si no tiene periodos presenciales, saltar esta sección
            if not tiene_presencial:
                continue
            
            secciones_incluidas += 1
            
            if not primera_pagina:
                elementos.append(PageBreak())
            primera_pagina = False
            
            datos = obtener_datos_horario_seccion(ciclo.id, seccion.id)
            if not datos['asignaciones'] and not datos['bloques']:
                continue
            
            grilla, horas = construir_grilla(datos['bloques'], datos['asignaciones'])
            
            # Encabezado de sección
            sec_style = ParagraphStyle('Sec', parent=styles['Heading2'],
                                        fontSize=14, textColor=colors.HexColor('#2C3E50'),
                                        spaceAfter=10)
            elementos.append(Paragraph(
                f"{carrera.nombre} - Semestre {seccion.semestre} - Sección {seccion.nombre}",
                sec_style
            ))
            
            # Tabla
            header = ['Hora'] + [DIAS_CORTO[d] for d in range(1, 8)]
            tabla_data = [header]
            
            for h in horas:
                bloque_ref = next((b for b in datos['bloques'] if b.hora_inicio == h), None)
                fila = [f"{h.strftime('%H:%M')}-{bloque_ref.hora_fin.strftime('%H:%M')}" if bloque_ref else h.strftime('%H:%M')]
                
                for d in range(1, 8):
                    celda = grilla[h].get(d)
                    if celda:
                        texto = f"<b>{celda['curso']}</b><br/>{celda['docente']}<br/><i>{MODALIDAD_NOMBRE.get(celda['modalidad'], celda['modalidad'])}</i>"
                        fila.append(Paragraph(texto, styles['Normal']))
                    else:
                        fila.append('')
                tabla_data.append(fila)
            
            tabla = Table(tabla_data, colWidths=[1.1*inch] + [1.3*inch]*7)
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#ECF0F1')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
            ])
            
            for i, h in enumerate(horas, start=1):
                for d in range(1, 8):
                    celda = grilla[h].get(d)
                    if celda:
                        color = MODALIDAD_COLOR.get(celda['modalidad'], '#FFFFFF')
                        style.add('BACKGROUND', (d, i), (d, i), colors.HexColor(color))
            
            tabla.setStyle(style)
            elementos.append(tabla)
    
    # Si no hay secciones con periodos presenciales, mostrar mensaje
    if secciones_incluidas == 0:
        elementos.append(Paragraph(
            "No hay secciones con periodos presenciales registradas en este ciclo.",
            styles['Normal']
        ))
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer