from flask import Flask, render_template, request, jsonify
from models import (db, Carrera, Seccion, Curso, Docente, Ciclo,
                    CicloCarrera, BloqueHorario, Asignacion, RestriccionDocente)
from flask_migrate import Migrate
from config import Config
from datetime import datetime, time
from reportes import (generar_pdf_seccion, generar_pdf_laboratorio, generar_pdf_todas_secciones,
                    generar_excel_todas_secciones, generar_excel_laboratorio, generar_pdf_docente, generar_pdf_todos_docentes, 
                    generar_pdf_vitrina_presencial)
from flask import send_file
from openpyxl import load_workbook
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)


# ============================================================
# Rutas de navegación principal
# ============================================================
@app.route('/')
def index():
    return render_template('base.html')


# ============================================================
# CRUD: Carreras
# ============================================================
@app.route('/carreras', methods=['GET', 'POST'])
def carreras():
    if request.method == 'POST':
        d = request.form
        c = Carrera(nombre=d['nombre'], codigo=d['codigo'])
        db.session.add(c)
        db.session.commit()
        return jsonify({'ok': True})
    return render_template('carreras.html', carreras=Carrera.query.order_by(Carrera.nombre).all())


# ============================================================
# CRUD: Secciones (Simplificado: semestre es un int)
# ============================================================
@app.route('/secciones', methods=['GET', 'POST'])
def secciones():
    if request.method == 'POST':
        d = request.form
        sec = Seccion(
            id_carrera=int(d['id_carrera']),
            semestre=int(d['semestre']),
            nombre=d['nombre']
        )
        db.session.add(sec)
        db.session.commit()
        return jsonify({'ok': True})

    carreras_list = Carrera.query.order_by(Carrera.nombre).all()
    secciones_data = db.session.query(Seccion, Carrera)\
        .join(Carrera, Seccion.id_carrera == Carrera.id)\
        .order_by(Carrera.nombre, Seccion.semestre, Seccion.nombre)\
        .all()
    return render_template('secciones.html', secciones=secciones_data, carreras=carreras_list)


# ============================================================
# CRUD: Cursos (Simplificado: semestre es un int)
# ============================================================
@app.route('/cursos', methods=['GET', 'POST'])
def cursos():
    if request.method == 'POST':
        d = request.form
        curso = Curso(
            nombre=d['nombre'],
            id_carrera=int(d['id_carrera']),
            semestre=int(d['semestre']),
            no_periodos_semanales=int(d['no_periodos']),
            duracion_bloque=int(d.get('duracion_bloque', 2))
        )
        db.session.add(curso)
        db.session.commit()
        return jsonify({'ok': True})

    carreras_list = Carrera.query.order_by(Carrera.nombre).all()
    return render_template('cursos.html', cursos=Curso.query.all(), carreras=carreras_list)


@app.route('/cursos/importar', methods=['POST'])
def importar_cursos():
    """Importa cursos desde un archivo Excel."""
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400

    archivo = request.files['archivo']
    if archivo.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400

    # Validar extensión
    if not archivo.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'error': 'El archivo debe ser Excel (.xlsx o .xls)'}), 400

    try:
        # Cargar el archivo Excel
        wb = load_workbook(archivo, read_only=True, data_only=True)
        ws = wb.active

        # Saltar encabezado
        filas = list(ws.iter_rows(min_row=2, values_only=True))

        if not filas:
            return jsonify({'error': 'El archivo no tiene datos (solo encabezado)'}), 400

        exitosos = []
        errores = []

        for idx, fila in enumerate(filas, start=2):  # Empezamos en fila 2 (datos)
            # Validar que la fila no esté vacía
            if not fila or all(c is None for c in fila[:5]):
                continue

            # Extraer valores (asegurarse de tener 5 columnas)
            fila_completa = list(fila) + [None] * (5 - len(fila))
            nombre, codigo_carrera, semestre, periodos, duracion = fila_completa[:5]

            # Validaciones
            errores_fila = []

            if not nombre or str(nombre).strip() == '':
                errores_fila.append('Nombre del curso vacío')
            else:
                nombre = str(nombre).strip()

            if not codigo_carrera:
                errores_fila.append('Código de carrera vacío')
            else:
                codigo_carrera = str(codigo_carrera).strip()
                # Buscar la carrera por código
                carrera = Carrera.query.filter_by(
                    codigo=codigo_carrera).first()
                if not carrera:
                    errores_fila.append(
                        f'Carrera con código "{codigo_carrera}" no existe')

            # Validar numéricos
            try:
                semestre = int(semestre) if semestre is not None else None
                if semestre is None or semestre < 1:
                    errores_fila.append('Semestre inválido (debe ser ≥ 1)')
            except (ValueError, TypeError):
                errores_fila.append(f'Semestre no numérico: "{semestre}"')

            try:
                periodos = int(periodos) if periodos is not None else None
                if periodos is None or periodos < 1:
                    errores_fila.append(
                        'Periodos semanales inválidos (debe ser ≥ 1)')
            except (ValueError, TypeError):
                errores_fila.append(f'Periodos no numéricos: "{periodos}"')

            try:
                duracion = int(duracion) if duracion is not None else 2
                if duracion < 1:
                    errores_fila.append(
                        'Duración de bloque inválida (debe ser ≥ 1)')
            except (ValueError, TypeError):
                errores_fila.append(f'Duración no numérica: "{duracion}"')

            # Si hay errores, registrarlos y saltar
            if errores_fila:
                errores.append({
                    'fila': idx,
                    'nombre': nombre or '(sin nombre)',
                    'errores': errores_fila
                })
                continue

            # Buscar la carrera (ya validada)
            carrera = Carrera.query.filter_by(codigo=codigo_carrera).first()

            # Crear el curso
            curso = Curso(
                nombre=nombre,
                id_carrera=carrera.id,
                semestre=semestre,
                no_periodos_semanales=periodos,
                duracion_bloque=duracion
            )
            db.session.add(curso)
            exitosos.append({
                'fila': idx,
                'nombre': nombre,
                'carrera': carrera.nombre,
                'semestre': semestre
            })

        # Confirmar todos los cambios
        db.session.commit()
        wb.close()

        return jsonify({
            'ok': True,
            'exitosos': exitosos,
            'errores': errores,
            'total_exitosos': len(exitosos),
            'total_errores': len(errores)
        })

    except Exception as e:
        return jsonify({'error': f'Error al procesar el archivo: {str(e)}'}), 500


@app.route('/cursos/plantilla')
def descargar_plantilla_cursos():
    """Descarga una plantilla Excel con los encabezados correctos."""
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from io import BytesIO

    wb = Workbook()
    ws = wb.active
    ws.title = "Plantilla Cursos"

    # Estilos
    header_fill = PatternFill(start_color="2C3E50",
                              end_color="2C3E50", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    # Encabezados
    headers = [
        'Nombre del Curso',
        'Código de Carrera',
        'Semestre',
        'Periodos Semanales',
        'Duración Bloque (horas)'
    ]

    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal='center')

    # Filas de ejemplo
    ejemplos = [
        ['Matemáticas I', 'ING-SIS', 1, 4, 2],
        ['Física I', 'ING-SIS', 1, 4, 2],
        ['Química General', 'QUI-BIO', 1, 6, 2],
        ['Anatomía I', 'MED', 1, 8, 3],
    ]

    for row_idx, ejemplo in enumerate(ejemplos, start=2):
        for col_idx, valor in enumerate(ejemplo, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=valor)
            cell.border = border

    # Ajustar anchos
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 20
    ws.column_dimensions['E'].width = 22

    # Hoja de instrucciones
    ws_inst = wb.create_sheet("Instrucciones")
    ws_inst['A1'] = "Instrucciones para la importación de cursos"
    ws_inst['A1'].font = Font(size=14, bold=True)

    instrucciones = [
        "",
        "1. La primera fila contiene los encabezados (no la modifiques).",
        "2. A partir de la segunda fila ingresa los datos de cada curso.",
        "3. Columna A: Nombre del curso (texto, obligatorio).",
        "4. Columna B: Código de carrera (debe existir en el sistema).",
        "5. Columna C: Semestre (número entero ≥ 1).",
        "6. Columna D: Periodos semanales / horas por semana (número entero ≥ 1).",
        "7. Columna E: Duración del bloque en horas (número entero ≥ 1, default 2).",
        "",
        "Notas importantes:",
        "- Las filas vacías se ignoran automáticamente.",
        "- Si una fila tiene error, se reporta pero el resto se importa.",
        "- Al final verás un resumen de cursos importados y errores encontrados.",
        "- El código de carrera debe coincidir EXACTAMENTE con el registrado.",
    ]

    for idx, texto in enumerate(instrucciones, start=2):
        ws_inst[f'A{idx}'] = texto

    ws_inst.column_dimensions['A'].width = 80

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='plantilla_cursos.xlsx'
    )

# ============================================================
# CRUD: Docentes
# ============================================================

def vacio_a_none(valor):
            if valor is None:
                return None
            valor = str(valor).strip()
            return valor if valor else None

@app.route('/docentes', methods=['GET', 'POST'])
def docentes():
    if request.method == 'POST':
        d = request.form
        # Función auxiliar para convertir strings vacíos en None

        docente = Docente(
            grado_academico=vacio_a_none(d.get('grado_academico')),
            nombres=d['nombres'].strip(),
            apellidos=d['apellidos'].strip(),
            telefono=vacio_a_none(d.get('telefono')),
            correo=vacio_a_none(d.get('correo'))
        )
        db.session.add(docente)
        db.session.commit()
        return jsonify({'ok': True})
    return render_template('docentes.html', docentes=Docente.query.order_by(Docente.grado_academico,Docente.nombres,Docente.apellidos).all())


# ============================================================
# CRUD: Ciclos
# ============================================================
@app.route('/ciclos', methods=['GET', 'POST'])
def ciclos():
    if request.method == 'POST':
        d = request.form
        ciclo = Ciclo(
            nombre=d['nombre'],
            fecha_inicio=datetime.strptime(
                d['fecha_inicio'], '%Y-%m-%d').date(),
            fecha_fin=datetime.strptime(d['fecha_fin'], '%Y-%m-%d').date()
        )
        db.session.add(ciclo)
        db.session.commit()
        return jsonify({'ok': True})
    return render_template('ciclos.html', ciclos=Ciclo.query.all())


# ============================================================
# Gestión de bloques horarios por ciclo (Variables y 7 días)
# ============================================================
@app.route('/api/seccion/<int:seccion_id>/bloques', methods=['GET', 'POST'])
def bloques_seccion(seccion_id):
    if request.method == 'GET':
        bloques = BloqueHorario.query.filter_by(id_seccion=seccion_id).all()
        return jsonify([{
            'id': b.id,
            'dia': b.dia,
            'hora_inicio': b.hora_inicio.strftime('%H:%M'),
            'hora_fin': b.hora_fin.strftime('%H:%M'),
            'tipo': b.tipo
        } for b in bloques])

    d = request.json
    # Obtener el ciclo al que pertenece esta sección (para validaciones futuras)
    sec = Seccion.query.get_or_404(seccion_id)

    b = BloqueHorario(
        id_seccion=seccion_id,
        dia=d['dia'],
        hora_inicio=datetime.strptime(d['hora_inicio'], '%H:%M').time(),
        hora_fin=datetime.strptime(d['hora_fin'], '%H:%M').time(),
        tipo=d.get('tipo', 'clase')
    )
    db.session.add(b)
    db.session.commit()
    return jsonify({'id': b.id})


@app.route('/api/seccion/<int:seccion_id>/bloques/generar', methods=['POST'])
def generar_bloques_seccion(seccion_id):
    """Genera bloques de clase considerando los recesos como intervalos vacíos."""
    d = request.json

    # 1. Eliminar asignaciones y bloques antiguos de ESTA sección
    Asignacion.query.filter_by(id_seccion=seccion_id).delete(
        synchronize_session=False)
    BloqueHorario.query.filter_by(
        id_seccion=seccion_id).delete(synchronize_session=False)
    db.session.commit()

    # 2. Parsear horas
    def hora_a_minutos(hora_str):
        h, m = map(int, hora_str.split(':'))
        return h * 60 + m

    inicio_min = hora_a_minutos(d['hora_inicio'])
    fin_min = hora_a_minutos(d['hora_fin'])
    duracion_min = int(d['duracion_min'])
    dias = d.get('dias', list(range(1, 8)))
    recesos = d.get('recesos', [])

    if inicio_min >= fin_min:
        return jsonify({'error': 'La hora de inicio debe ser menor a la hora de fin'}), 400

    # 3. Convertir recesos a tuplas de (inicio, fin) en minutos
    recesos_min = []
    for receso in recesos:
        r_inicio = hora_a_minutos(receso['hora_inicio'])
        r_fin = hora_a_minutos(receso['hora_fin'])
        if r_inicio < r_fin:
            recesos_min.append((r_inicio, r_fin))

    # Ordenar recesos por hora de inicio
    recesos_min.sort(key=lambda x: x[0])

    # 4. Generar bloques para cada día
    for dia in dias:
        h = inicio_min

        while h + duracion_min <= fin_min:
            # Verificar si el bloque actual cae en algún receso
            bloque_inicio = h
            bloque_fin = h + duracion_min

            # Buscar si hay traslape con algún receso
            en_receso = False
            for r_inicio, r_fin in recesos_min:
                # Si el bloque traslape con el receso
                if bloque_inicio < r_fin and r_inicio < bloque_fin:
                    # Saltar hasta el final del receso
                    h = r_fin
                    en_receso = True
                    break

            if en_receso:
                continue

            # Si no hay traslape, crear el bloque de clase
            hi = time(h // 60, h % 60)
            hf = time((h + duracion_min) // 60, (h + duracion_min) % 60)
            db.session.add(BloqueHorario(
                id_seccion=seccion_id, dia=dia,
                hora_inicio=hi, hora_fin=hf, tipo='clase'
            ))
            h += duracion_min

        # 5. Insertar los recesos para este día
        for r_inicio, r_fin in recesos_min:
            receso_inicio = time(r_inicio // 60, r_inicio % 60)
            receso_fin = time(r_fin // 60, r_fin % 60)
            db.session.add(BloqueHorario(
                id_seccion=seccion_id, dia=dia,
                hora_inicio=receso_inicio, hora_fin=receso_fin, tipo='receso'
            ))

    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/seccion/<int:seccion_id>/bloques/receso', methods=['POST'])
def agregar_receso(seccion_id):
    """Inserta un receso y desplaza los bloques posteriores exactamente la duración del receso."""
    d = request.json

    dia = int(d['dia'])
    hora_inicio = datetime.strptime(d['hora_inicio'], '%H:%M').time()
    hora_fin = datetime.strptime(d['hora_fin'], '%H:%M').time()

    if hora_inicio >= hora_fin:
        return jsonify({'error': 'La hora de inicio debe ser menor a la hora de fin'}), 400

    inicio_receso = hora_inicio.hour * 60 + hora_inicio.minute
    fin_receso = hora_fin.hour * 60 + hora_fin.minute
    duracion_receso = fin_receso - inicio_receso

    # Obtener bloques del mismo día ordenados por hora
    bloques = BloqueHorario.query.filter_by(
        id_seccion=seccion_id, dia=dia
    ).order_by(BloqueHorario.hora_inicio).all()

    # Lista para los nuevos bloques que se crearán después del desplazamiento
    nuevos_bloques = []

    for bloque in bloques:
        b_inicio = bloque.hora_inicio.hour * 60 + bloque.hora_inicio.minute
        b_fin = bloque.hora_fin.hour * 60 + bloque.hora_fin.minute
        duracion_bloque = b_fin - b_inicio

        # CASO 1: Bloque termina antes o justo al inicio del receso
        # → No se toca, se mantiene
        if b_fin <= inicio_receso:
            continue

        # CASO 2: Bloque empieza después o justo al fin del receso
        # → Se elimina y se recrea desplazado
        elif b_inicio >= fin_receso:
            nuevo_inicio = b_inicio + duracion_receso
            nuevo_fin = b_fin + duracion_receso

            if nuevo_fin <= 22 * 60:  # No exceder las 22:00
                # Guardar info para crear nuevo bloque después
                nuevos_bloques.append({
                    'dia': dia,
                    'hora_inicio': time(nuevo_inicio // 60, nuevo_inicio % 60),
                    'hora_fin': time(nuevo_fin // 60, nuevo_fin % 60),
                    'tipo': bloque.tipo
                })

            # Eliminar bloque original y sus asignaciones
            Asignacion.query.filter_by(id_bloque=bloque.id).delete(
                synchronize_session=False)
            db.session.delete(bloque)

        # CASO 3: Cualquier tipo de traslape con el receso
        # → Se elimina completamente
        else:
            Asignacion.query.filter_by(id_bloque=bloque.id).delete(
                synchronize_session=False)
            db.session.delete(bloque)

    # Insertar el receso
    receso = BloqueHorario(
        id_seccion=seccion_id, dia=dia,
        hora_inicio=hora_inicio, hora_fin=hora_fin,
        tipo='receso'
    )
    db.session.add(receso)

    # Crear los nuevos bloques desplazados
    for nb in nuevos_bloques:
        nuevo_bloque = BloqueHorario(
            id_seccion=seccion_id,
            dia=nb['dia'],
            hora_inicio=nb['hora_inicio'],
            hora_fin=nb['hora_fin'],
            tipo=nb['tipo']
        )
        db.session.add(nuevo_bloque)

    # Confirmar todos los cambios
    db.session.commit()

    return jsonify({'id': receso.id})


@app.route('/api/seccion/<int:seccion_id>/bloques/<int:bloque_id>', methods=['DELETE'])
def eliminar_bloque_seccion(seccion_id, bloque_id):
    """Elimina un bloque (clase o receso) de la sección."""
    bloque = BloqueHorario.query.get_or_404(bloque_id)

    # Si es un bloque de clase con asignaciones, no permitir eliminar
    if bloque.tipo == 'clase':
        asignaciones = Asignacion.query.filter_by(id_bloque=bloque_id).count()
        if asignaciones > 0:
            return jsonify({
                'error': f'No se puede eliminar este bloque porque tiene {asignaciones} clase(s) asignada(s). Elimina las clases primero.'
            }), 400

    db.session.delete(bloque)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/ciclo/<int:ciclo_id>/bloques/<int:bloque_id>', methods=['DELETE'])
def eliminar_bloque(ciclo_id, bloque_id):
    b = BloqueHorario.query.get_or_404(bloque_id)
    db.session.delete(b)
    db.session.commit()
    return jsonify({'ok': True})


# ============================================================
# Carreras activas por ciclo
# ============================================================
@app.route('/api/ciclo/<int:ciclo_id>/carreras', methods=['GET', 'POST'])
def set_carreras_ciclo(ciclo_id):
    if request.method == 'GET':
        rows = CicloCarrera.query.filter_by(id_ciclo=ciclo_id).all()
        return jsonify([r.id_carrera for r in rows])

    if request.method == 'POST':
        CicloCarrera.query.filter_by(id_ciclo=ciclo_id).delete()
        for cid in request.json.get('carreras', []):
            db.session.add(CicloCarrera(id_ciclo=ciclo_id, id_carrera=cid))
        db.session.commit()
        return jsonify({'ok': True})


@app.route('/api/carreras')
def listar_carreras():
    return jsonify([{'id': c.id, 'nombre': c.nombre} for c in Carrera.query.order_by(Carrera.nombre).all()])


@app.route('/api/docentes')
def listar_docentes():
    docentes = Docente.query.order_by(Docente.grado_academico,Docente.nombres,Docente.apellidos).all()
    return jsonify([{'id': d.id, 'nombre': d.nombre_con_grado} for d in docentes])


@app.route('/api/docente/<int:docente_id>/restricciones', methods=['GET', 'POST'])
def restricciones_docente(docente_id):
    """Obtiene o crea restricciones de horario para un docente."""
    if request.method == 'GET':
        restricciones = RestriccionDocente.query.filter_by(
            id_docente=docente_id).all()
        return jsonify([{
            'id': r.id,
            'dia': r.dia,
            'hora_inicio': r.hora_inicio.strftime('%H:%M'),
            'hora_fin': r.hora_fin.strftime('%H:%M'),
            'motivo': r.motivo
        } for r in restricciones])

    # POST: Crear nueva restricción
    d = request.json
    restriccion = RestriccionDocente(
        id_docente=docente_id,
        dia=int(d['dia']),
        hora_inicio=datetime.strptime(d['hora_inicio'], '%H:%M').time(),
        hora_fin=datetime.strptime(d['hora_fin'], '%H:%M').time(),
        motivo=d.get('motivo', '')
    )
    db.session.add(restriccion)
    db.session.commit()
    return jsonify({'id': restriccion.id})


@app.route('/api/docente/<int:docente_id>/restricciones/<int:restriccion_id>', methods=['DELETE'])
def eliminar_restriccion(docente_id, restriccion_id):
    """Elimina una restricción de horario."""
    restriccion = RestriccionDocente.query.get_or_404(restriccion_id)
    db.session.delete(restriccion)
    db.session.commit()
    return jsonify({'ok': True})

# ============================================================
# Horario: Vistas y APIs
# ============================================================


@app.route('/horario/<int:ciclo_id>')
def horario(ciclo_id):
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    return render_template('horario.html', ciclo=ciclo)


@app.route('/api/horario/datos/<int:ciclo_id>')
def horario_datos(ciclo_id):
    """Obtiene todas las asignaciones del ciclo con sus relaciones."""
    asignaciones = Asignacion.query.filter_by(id_ciclo=ciclo_id).all()
    result = []
    for a in asignaciones:
        result.append({
            'id': a.id,
            'bloque_id': a.id_bloque,
            'dia': a.bloque.dia,
            'hora_inicio': a.bloque.hora_inicio.strftime('%H:%M'),
            'hora_fin': a.bloque.hora_fin.strftime('%H:%M'),
            'curso': a.curso.nombre,
            'curso_id': a.id_curso,
            'seccion': a.seccion.nombre,
            'seccion_id': a.id_seccion,
            'docente': a.docente.nombre_con_grado if a.docente else None,
            'docente_id': a.id_docente,
            'modalidad': a.modalidad
        })
    return jsonify(result)


@app.route('/api/horario/secciones/<int:ciclo_id>')
def secciones_activas(ciclo_id):
    """Obtiene las secciones de las carreras activas en este ciclo."""
    rows = db.session.query(Seccion, Carrera)\
        .join(Carrera, Seccion.id_carrera == Carrera.id)\
        .join(CicloCarrera, Carrera.id == CicloCarrera.id_carrera)\
        .filter(CicloCarrera.id_ciclo == ciclo_id)\
        .order_by(Carrera.nombre, Seccion.semestre, Seccion.nombre)\
        .all()

    result = []
    for sec, car in rows:
        result.append({
            'seccion_id': sec.id,
            'seccion': sec.nombre,
            'semestre': sec.semestre,
            'carrera': car.nombre,
            'carrera_id': car.id
        })
    return jsonify(result)


@app.route('/api/horario/cursos/<int:seccion_id>')
def cursos_seccion(seccion_id):
    """Obtiene los cursos que coinciden con la carrera y semestre de la sección."""
    sec = Seccion.query.get_or_404(seccion_id)
    cursos = Curso.query.filter_by(
        id_carrera=sec.id_carrera,
        semestre=sec.semestre
    ).all()

    return jsonify([{
        'id': c.id,
        'nombre': c.nombre,
        'periodos': c.no_periodos_semanales
    } for c in cursos])


# ============================================================
# Validación de traslapes
# ============================================================
@app.route('/api/validar_traslape', methods=['POST'])
def validar_traslape():
    """Detecta traslapes por intervalos de tiempo y restricciones del docente."""
    d = request.json
    docente_id = d.get('docente_id')
    bloque_id = d.get('bloque_id')
    asignacion_id = d.get('asignacion_id')
    ciclo_id = d.get('ciclo_id')

    if not docente_id or not bloque_id or not ciclo_id:
        return jsonify({'conflicto': False})

    # Obtener el intervalo de tiempo del bloque objetivo
    bloque_target = BloqueHorario.query.get(bloque_id)
    if not bloque_target:
        return jsonify({'conflicto': False})

    target_inicio_min = bloque_target.hora_inicio.hour * \
        60 + bloque_target.hora_inicio.minute
    target_fin_min = bloque_target.hora_fin.hour * 60 + bloque_target.hora_fin.minute

    # ---------------------------------------------------------
    # 1. Verificar restricciones de horario del docente
    # ---------------------------------------------------------
    restricciones = RestriccionDocente.query.filter_by(
        id_docente=docente_id,
        dia=bloque_target.dia
    ).all()

    for restriccion in restricciones:
        r_inicio_min = restriccion.hora_inicio.hour * 60 + restriccion.hora_inicio.minute
        r_fin_min = restriccion.hora_fin.hour * 60 + restriccion.hora_fin.minute

        # Verificar traslape con la restricción
        if target_inicio_min < r_fin_min and r_inicio_min < target_fin_min:
            motivo = f" ({restriccion.motivo})" if restriccion.motivo else ""
            return jsonify({
                'conflicto': True,
                'mensaje': f"El docente tiene una restricción de horario{motivo} "
                f"el {DIAS_NOMBRE[bloque_target.dia]} de "
                f"{restriccion.hora_inicio.strftime('%H:%M')} a "
                f"{restriccion.hora_fin.strftime('%H:%M')}."
            })

    # ---------------------------------------------------------
    # 2. Verificar traslape con otras asignaciones del docente
    # ---------------------------------------------------------
    asignaciones_docente = db.session.query(Asignacion).join(BloqueHorario).filter(
        Asignacion.id_docente == docente_id,
        Asignacion.id_ciclo == ciclo_id,
        BloqueHorario.dia == bloque_target.dia
    )

    if asignacion_id:
        asignaciones_docente = asignaciones_docente.filter(
            Asignacion.id != asignacion_id)

    for asignacion in asignaciones_docente.all():
        bloque_existente = asignacion.bloque
        existente_inicio_min = bloque_existente.hora_inicio.hour * \
            60 + bloque_existente.hora_inicio.minute
        existente_fin_min = bloque_existente.hora_fin.hour * \
            60 + bloque_existente.hora_fin.minute

        if target_inicio_min < existente_fin_min and existente_inicio_min < target_fin_min:
            sec_conflicto = Seccion.query.get(asignacion.id_seccion)
            nombre_seccion = f"{sec_conflicto.nombre}" if sec_conflicto else "otra sección"

            traslape_inicio = max(target_inicio_min, existente_inicio_min)
            traslape_fin = min(target_fin_min, existente_fin_min)
            minutos_traslape = traslape_fin - traslape_inicio

            return jsonify({
                'conflicto': True,
                'mensaje': f"El docente ya tiene asignada la clase '{asignacion.curso.nombre}' "
                f"en la Sección {nombre_seccion} "
                f"({bloque_existente.hora_inicio.strftime('%H:%M')}-"
                f"{bloque_existente.hora_fin.strftime('%H:%M')}). "
                f"Traslape de {minutos_traslape} minutos."
            })

    return jsonify({'conflicto': False})


# Constante para los nombres de días
DIAS_NOMBRE = ['', 'Lunes', 'Martes', 'Miércoles',
               'Jueves', 'Viernes', 'Sábado', 'Domingo']


@app.route('/api/validar_laboratorio', methods=['POST'])
def validar_laboratorio():
    """Verifica si ya existe otra asignación con el mismo laboratorio en el mismo día y hora."""
    d = request.json
    modalidad = d.get('modalidad')
    bloque_id = int(d.get('bloque_id')) if d.get('bloque_id') else None
    asignacion_id = int(d.get('asignacion_id')) if d.get(
        'asignacion_id') else None
    ciclo_id = int(d.get('ciclo_id')) if d.get('ciclo_id') else None

    if modalidad not in ['laboratorio_escuela', 'laboratorio_radiologia']:
        return jsonify({'conflicto': False})

    if not bloque_id or not ciclo_id:
        return jsonify({'conflicto': False})

    # Obtener el día y hora del bloque que queremos validar
    bloque_objetivo = BloqueHorario.query.get(bloque_id)
    if not bloque_objetivo:
        return jsonify({'conflicto': False})

    dia_objetivo = bloque_objetivo.dia
    hora_inicio_objetivo = bloque_objetivo.hora_inicio
    hora_fin_objetivo = bloque_objetivo.hora_fin

    # Convertir a minutos para comparar intervalos
    obj_inicio_min = hora_inicio_objetivo.hour * 60 + hora_inicio_objetivo.minute
    obj_fin_min = hora_fin_objetivo.hour * 60 + hora_fin_objetivo.minute

    # Buscar TODAS las asignaciones del ciclo con la misma modalidad de laboratorio
    # que tengan un bloque el mismo día con horario que se traslape
    asignaciones_lab = db.session.query(Asignacion).join(BloqueHorario).filter(
        Asignacion.id_ciclo == ciclo_id,
        Asignacion.modalidad == modalidad,
        BloqueHorario.dia == dia_objetivo
    )

    if asignacion_id:
        asignaciones_lab = asignaciones_lab.filter(
            Asignacion.id != asignacion_id)

    # Verificar traslape por intervalos de tiempo
    for asignacion in asignaciones_lab.all():
        b = asignacion.bloque
        b_inicio_min = b.hora_inicio.hour * 60 + b.hora_inicio.minute
        b_fin_min = b.hora_fin.hour * 60 + b.hora_fin.minute

        # Dos intervalos se traslapan si: A_inicio < B_fin Y B_inicio < A_fin
        if obj_inicio_min < b_fin_min and b_inicio_min < obj_fin_min:
            sec_conflicto = Seccion.query.get(asignacion.id_seccion)
            nombre_seccion = sec_conflicto.nombre if sec_conflicto else "otra sección"
            carrera = Carrera.query.get(
                sec_conflicto.id_carrera) if sec_conflicto else None
            nombre_carrera = carrera.nombre if carrera else ""

            nombre_lab = "Laboratorio Escuela" if modalidad == 'laboratorio_escuela' else "Laboratorio Radiología"

            return jsonify({
                'conflicto': True,
                'mensaje': f"El {nombre_lab} ya está ocupado en ese horario por el curso '{asignacion.curso.nombre}' "
                f"de la Sección {nombre_seccion} ({nombre_carrera})."
            })

    return jsonify({'conflicto': False})


# ============================================================
# CRUD: Asignaciones
# ============================================================
@app.route('/api/asignacion', methods=['POST'])
def crear_asignacion():
    d = request.json
    a = Asignacion(
        id_ciclo=d['ciclo_id'],
        id_seccion=d['seccion_id'],
        id_curso=d['curso_id'],
        id_docente=d.get('docente_id'),
        id_bloque=d['bloque_id'],
        modalidad=d.get('modalidad', 'presencial')
    )
    db.session.add(a)
    db.session.commit()
    return jsonify({'id': a.id})


@app.route('/api/asignacion/<int:id>', methods=['PUT'])
def actualizar_asignacion(id):
    a = Asignacion.query.get_or_404(id)
    d = request.json
    if 'bloque_id' in d:
        a.id_bloque = d['bloque_id']
    if 'docente_id' in d:
        a.id_docente = d['docente_id']
    if 'modalidad' in d:
        a.modalidad = d['modalidad']
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/asignacion/<int:id>/propagar-docente', methods=['POST'])
def propagar_docente(id):
    """Propaga el docente a todos los periodos del mismo curso en la misma sección y ciclo."""
    d = request.json
    docente_id = d.get('docente_id')
    
    if not docente_id:
        return jsonify({'error': 'Debe seleccionar un docente'}), 400
    
    asignacion_base = Asignacion.query.get_or_404(id)
    
    # Buscar todas las asignaciones del MISMO curso en la MISMA sección del MISMO ciclo
    asignaciones_curso = Asignacion.query.filter_by(
        id_ciclo=asignacion_base.id_ciclo,
        id_seccion=asignacion_base.id_seccion,
        id_curso=asignacion_base.id_curso
    ).all()
    
    # Obtener IDs de las asignaciones del curso para excluir de la búsqueda de conflictos
    ids_asignaciones_curso = [a.id for a in asignaciones_curso]
    
    conflictos = []
    for asignacion in asignaciones_curso:
        if asignacion.id == id:
            continue  # La base ya se validó antes
        
        # ← NUEVO: Si ya tiene el mismo docente, no hay nada que hacer
        if asignacion.id_docente == docente_id:
            continue
        
        bloque_objetivo = asignacion.bloque
        
        # Buscar conflictos EXCLUYENDO las asignaciones del mismo curso
        conflicto = db.session.query(Asignacion).join(BloqueHorario).filter(
            Asignacion.id_docente == docente_id,
            Asignacion.id_ciclo == asignacion_base.id_ciclo,
            BloqueHorario.dia == bloque_objetivo.dia,
            Asignacion.id.notin_(ids_asignaciones_curso)  # ← EXCLUIR asignaciones del mismo curso
        ).first()
        
        if conflicto:
            b_conf = conflicto.bloque
            conf_inicio = b_conf.hora_inicio.hour * 60 + b_conf.hora_inicio.minute
            conf_fin = b_conf.hora_fin.hour * 60 + b_conf.hora_fin.minute
            obj_inicio = bloque_objetivo.hora_inicio.hour * 60 + bloque_objetivo.hora_inicio.minute
            obj_fin = bloque_objetivo.hora_fin.hour * 60 + bloque_objetivo.hora_fin.minute
            
            if obj_inicio < conf_fin and conf_inicio < obj_fin:
                conflictos.append({
                    'bloque': f"{DIAS_NOMBRE[bloque_objetivo.dia]} {bloque_objetivo.hora_inicio.strftime('%H:%M')}-{bloque_objetivo.hora_fin.strftime('%H:%M')}",
                    'curso_conflicto': conflicto.curso.nombre
                })
    
    if conflictos:
        mensaje = "No se puede propagar el docente por los siguientes traslapes:\n"
        for c in conflictos:
            mensaje += f"  • En {c['bloque']}, el docente ya imparte '{c['curso_conflicto']}'\n"
        return jsonify({'error': mensaje}), 400
    
    # Propagar el docente solo a las asignaciones que no lo tienen
    actualizadas = 0
    for asignacion in asignaciones_curso:
        if asignacion.id_docente != docente_id:
            asignacion.id_docente = docente_id
            actualizadas += 1
    
    db.session.commit()
    
    return jsonify({
        'ok': True,
        'actualizadas': actualizadas,
        'total': len(asignaciones_curso)
    })


# Constante para los nombres de días (necesaria en el endpoint anterior)
DIAS_NOMBRE = ['', 'Lunes', 'Martes', 'Miércoles',
               'Jueves', 'Viernes', 'Sábado', 'Domingo']


@app.route('/api/asignacion/<int:id>', methods=['DELETE'])
def eliminar_asignacion(id):
    a = Asignacion.query.get_or_404(id)
    db.session.delete(a)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/horario/datos/<int:ciclo_id>/<int:seccion_id>')
def horario_datos_seccion(ciclo_id, seccion_id):
    """Obtiene las asignaciones del ciclo filtradas por sección."""
    asignaciones = Asignacion.query.filter_by(
        id_ciclo=ciclo_id,
        id_seccion=seccion_id
    ).all()

    result = []
    for a in asignaciones:
        result.append({
            'id': a.id,
            'bloque_id': a.id_bloque,
            'dia': a.bloque.dia,
            'hora_inicio': a.bloque.hora_inicio.strftime('%H:%M'),
            'hora_fin': a.bloque.hora_fin.strftime('%H:%M'),
            'curso': a.curso.nombre,
            'curso_id': a.id_curso,
            'seccion': a.seccion.nombre,
            'seccion_id': a.id_seccion,
            'docente': a.docente.nombre_con_grado if a.docente else None,
            'docente_id': a.id_docente,
            'modalidad': a.modalidad
        })
    return jsonify(result)

# ============================================================
# Reportería: Vistas
# ============================================================
@app.route('/reportes')
def reportes():
    """Página principal de reportería."""
    ciclos = Ciclo.query.all()
    return render_template('reportes.html', ciclos=ciclos)


@app.route('/reportes/seccion/<int:ciclo_id>')
def reporte_seccion(ciclo_id):
    """Vista de horario por sección (solo lectura)."""
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    return render_template('reporte_seccion.html', ciclo=ciclo)


@app.route('/reportes/laboratorio/<int:ciclo_id>')
def reporte_laboratorio(ciclo_id):
    """Vista de horario por laboratorio (solo lectura)."""
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    return render_template('reporte_laboratorio.html', ciclo=ciclo)


@app.route('/reportes/docente/<int:ciclo_id>')
def reporte_docente(ciclo_id):
    """Vista de horario por docente (solo lectura)."""
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    return render_template('reporte_docente.html', ciclo=ciclo)


# ============================================================
# Reportería: APIs para vistas de solo lectura
# ============================================================
@app.route('/api/reporte/seccion/<int:ciclo_id>/<int:seccion_id>')
def api_reporte_seccion(ciclo_id, seccion_id):
    """Devuelve los datos del horario de una sección."""
    from reportes import obtener_datos_horario_seccion, DIAS_NOMBRE, MODALIDAD_NOMBRE
    
    datos = obtener_datos_horario_seccion(ciclo_id, seccion_id)
    seccion = Seccion.query.get_or_404(seccion_id)
    carrera = Carrera.query.get(seccion.id_carrera)
    
    bloques = [{
        'id': b.id, 'dia': b.dia,
        'hora_inicio': b.hora_inicio.strftime('%H:%M'),
        'hora_fin': b.hora_fin.strftime('%H:%M'),
        'tipo': b.tipo
    } for b in datos['bloques']]
    
    asignaciones = [{
        'id': a.id, 'bloque_id': a.id_bloque,
        'dia': a.bloque.dia,
        'hora_inicio': a.bloque.hora_inicio.strftime('%H:%M'),
        'hora_fin': a.bloque.hora_fin.strftime('%H:%M'),
        'curso': a.curso.nombre,
        'docente': a.docente.nombre_con_grado if a.docente else '—',
        'modalidad': MODALIDAD_NOMBRE.get(a.modalidad, a.modalidad)
    } for a in datos['asignaciones']]
    
    return jsonify({
        'seccion': f"{carrera.nombre} - Semestre {seccion.semestre} - Sección {seccion.nombre}",
        'bloques': bloques,
        'asignaciones': asignaciones
    })


@app.route('/api/reporte/laboratorio/<int:ciclo_id>/<modalidad>')
def api_reporte_laboratorio(ciclo_id, modalidad):
    """Devuelve los datos del horario de un laboratorio."""
    from reportes import MODALIDAD_NOMBRE
    
    if modalidad not in ['laboratorio_escuela', 'laboratorio_radiologia']:
        return jsonify({'error': 'Modalidad inválida'}), 400
    
    asignaciones = Asignacion.query.filter_by(
        id_ciclo=ciclo_id, modalidad=modalidad
    ).all()
    
    resultado = []
    for a in asignaciones:
        sec = a.seccion
        carrera = Carrera.query.get(a.curso.id_carrera)
        resultado.append({
            'id': a.id,
            'dia': a.bloque.dia,
            'hora_inicio': a.bloque.hora_inicio.strftime('%H:%M'),
            'hora_fin': a.bloque.hora_fin.strftime('%H:%M'),
            'curso': a.curso.nombre,
            'docente': a.docente.nombre_con_grado if a.docente else '—',
            'carrera': carrera.nombre if carrera else '',
            'seccion': f"Sem {sec.semestre}-{sec.nombre}"
        })
    
    return jsonify({
        'nombre': MODALIDAD_NOMBRE.get(modalidad, modalidad),
        'asignaciones': resultado
    })


@app.route('/api/reporte/docente/<int:ciclo_id>/<int:docente_id>')
def api_reporte_docente(ciclo_id, docente_id):
    """Devuelve los datos del horario de un docente."""
    from reportes import MODALIDAD_NOMBRE
    
    docente = Docente.query.get_or_404(docente_id)
    asignaciones = Asignacion.query.filter_by(
        id_ciclo=ciclo_id, id_docente=docente_id
    ).all()
    
    resultado = []
    for a in asignaciones:
        sec = a.seccion
        carrera = Carrera.query.get(a.curso.id_carrera)
        resultado.append({
            'id': a.id,
            'dia': a.bloque.dia,
            'hora_inicio': a.bloque.hora_inicio.strftime('%H:%M'),
            'hora_fin': a.bloque.hora_fin.strftime('%H:%M'),
            'curso': a.curso.nombre,
            'carrera': carrera.nombre if carrera else '',
            'seccion': f"Sem {sec.semestre}-{sec.nombre}",
            'modalidad': MODALIDAD_NOMBRE.get(a.modalidad, a.modalidad)
        })
    
    return jsonify({
        'docente': docente.nombre_con_grado,
        'grado': docente.grado_academico or '',
        'correo': docente.correo or '',
        'asignaciones': resultado
    })


# ============================================================
# Reportería: Descargas (PDF y Excel)
# ============================================================
@app.route('/descargar/pdf/seccion/<int:ciclo_id>/<int:seccion_id>')
def descargar_pdf_seccion(ciclo_id, seccion_id):
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    seccion = Seccion.query.get_or_404(seccion_id)
    carrera = Carrera.query.get(seccion.id_carrera)
    
    pdf = generar_pdf_seccion(ciclo, seccion, carrera)
    filename = f"horario_{carrera.codigo}_{seccion.semestre}_{seccion.nombre}_{ciclo.nombre}.pdf"
    return send_file(pdf, mimetype='application/pdf', as_attachment=True, download_name=filename)


@app.route('/descargar/excel/seccion/<int:ciclo_id>/<int:seccion_id>')
def descargar_excel_seccion(ciclo_id, seccion_id):
    """Excel individual de una sección (usa el mismo formato de lista)."""
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from io import BytesIO
    from reportes import MODALIDAD_NOMBRE
    
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    seccion = Seccion.query.get_or_404(seccion_id)
    carrera = Carrera.query.get(seccion.id_carrera)
    
    wb = Workbook()
    ws = wb.active
    ws.title = f"Sem{seccion.semestre}-{seccion.nombre}"
    
    header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    ws.merge_cells('A1:I1')
    ws['A1'] = f"{carrera.nombre} - Semestre {seccion.semestre} - Sección {seccion.nombre}"
    ws['A1'].font = Font(size=14, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    ws.merge_cells('A2:I2')
    ws['A2'] = f"Ciclo: {ciclo.nombre}"
    ws['A2'].alignment = Alignment(horizontal='center')
    
    headers = ['Día', 'Hora Inicio', 'Hora Fin', 'Curso', 'Docente', 'Modalidad']
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal='center')
    
    asignaciones = Asignacion.query.filter_by(
        id_ciclo=ciclo_id, id_seccion=seccion_id
    ).order_by(BloqueHorario.dia, BloqueHorario.hora_inicio).join(
        BloqueHorario, Asignacion.id_bloque == BloqueHorario.id
    ).all()
    
    row = 5
    for a in asignaciones:
        ws.cell(row=row, column=1, value=DIAS_NOMBRE[a.bloque.dia]).border = border
        ws.cell(row=row, column=2, value=a.bloque.hora_inicio.strftime('%H:%M')).border = border
        ws.cell(row=row, column=3, value=a.bloque.hora_fin.strftime('%H:%M')).border = border
        ws.cell(row=row, column=4, value=a.curso.nombre).border = border
        ws.cell(row=row, column=5, value=a.docente.nombre_con_grado if a.docente else '—').border = border
        ws.cell(row=row, column=6, value=MODALIDAD_NOMBRE.get(a.modalidad, a.modalidad)).border = border
        row += 1
    
    ws.column_dimensions['A'].width = 12
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 25
    ws.column_dimensions['E'].width = 25
    ws.column_dimensions['F'].width = 18
    
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"horario_{carrera.codigo}_{seccion.semestre}_{seccion.nombre}_{ciclo.nombre}.xlsx"
    return send_file(buffer, 
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True, download_name=filename)


@app.route('/descargar/pdf/laboratorio/<int:ciclo_id>/<modalidad>')
def descargar_pdf_laboratorio(ciclo_id, modalidad):
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    pdf = generar_pdf_laboratorio(ciclo, modalidad)
    from reportes import MODALIDAD_NOMBRE
    nombre = MODALIDAD_NOMBRE.get(modalidad, modalidad).replace(' ', '_')
    filename = f"horario_{nombre}_{ciclo.nombre}.pdf"
    return send_file(pdf, mimetype='application/pdf', as_attachment=True, download_name=filename)


@app.route('/descargar/excel/laboratorio/<int:ciclo_id>/<modalidad>')
def descargar_excel_laboratorio(ciclo_id, modalidad):
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    excel = generar_excel_laboratorio(ciclo, modalidad)
    from reportes import MODALIDAD_NOMBRE
    nombre = MODALIDAD_NOMBRE.get(modalidad, modalidad).replace(' ', '_')
    filename = f"horario_{nombre}_{ciclo.nombre}.xlsx"
    return send_file(excel,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True, download_name=filename)


@app.route('/descargar/pdf/todas-secciones/<int:ciclo_id>')
def descargar_pdf_todas_secciones(ciclo_id):
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    pdf = generar_pdf_todas_secciones(ciclo)
    filename = f"horarios_completos_{ciclo.nombre}.pdf"
    return send_file(pdf, mimetype='application/pdf', as_attachment=True, download_name=filename)

@app.route('/descargar/pdf/vitrina-presencial/<int:ciclo_id>')
def descargar_pdf_vitrina_presencial(ciclo_id):
    """Descarga PDF de vitrina solo con secciones que tienen periodos presenciales."""
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    pdf = generar_pdf_vitrina_presencial(ciclo)
    filename = f"vitrina_presencial_{ciclo.nombre}.pdf"
    return send_file(pdf, mimetype='application/pdf', as_attachment=True, download_name=filename)

@app.route('/descargar/excel/todas-secciones/<int:ciclo_id>')
def descargar_excel_todas_secciones(ciclo_id):
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    excel = generar_excel_todas_secciones(ciclo)
    filename = f"horarios_completos_{ciclo.nombre}.xlsx"
    return send_file(excel,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True, download_name=filename)


@app.route('/descargar/pdf/docente/<int:ciclo_id>/<int:docente_id>')
def descargar_pdf_docente(ciclo_id, docente_id):
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    docente = Docente.query.get_or_404(docente_id)
    pdf = generar_pdf_docente(ciclo, docente)
    filename = f"horario_{docente.apellidos}_{docente.nombres}_{ciclo.nombre}.pdf".replace(' ', '_')
    return send_file(pdf, mimetype='application/pdf', as_attachment=True, download_name=filename)


@app.route('/descargar/pdf/todos-docentes/<int:ciclo_id>')
def descargar_pdf_todos_docentes(ciclo_id):
    ciclo = Ciclo.query.get_or_404(ciclo_id)
    pdf = generar_pdf_todos_docentes(ciclo)
    filename = f"horarios_docentes_{ciclo.nombre}.pdf"
    return send_file(pdf, mimetype='application/pdf', as_attachment=True, download_name=filename)

#with app.app_context():
#    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5008, threaded=True, debug=True)
