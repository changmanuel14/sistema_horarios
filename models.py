from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Carrera(db.Model):
    __tablename__ = 'carrera'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    codigo = db.Column(db.String(20), unique=True, nullable=False)

class Seccion(db.Model):
    __tablename__ = 'seccion'
    id = db.Column(db.Integer, primary_key=True)
    id_carrera = db.Column(db.Integer, db.ForeignKey('carrera.id'), nullable=False)
    semestre = db.Column(db.Integer, nullable=False)  # Número de semestre (1, 2, 3...)
    nombre = db.Column(db.String(10), nullable=False) # Ej: 'A', 'B', '1'

class Curso(db.Model):
    __tablename__ = 'curso'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    id_carrera = db.Column(db.Integer, db.ForeignKey('carrera.id'), nullable=False)
    semestre = db.Column(db.Integer, nullable=False)  # Número de semestre (1, 2, 3...)
    no_periodos_semanales = db.Column(db.Integer, nullable=False)
    duracion_bloque = db.Column(db.Integer, default=2)
    
    carrera = db.relationship('Carrera')


class Docente(db.Model):
    __tablename__ = 'docente'
    id = db.Column(db.Integer, primary_key=True)
    grado_academico = db.Column(db.String(50))
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20))
    correo = db.Column(db.String(100))

    @property
    def nombre_completo(self):
        return f"{self.apellidos}, {self.nombres}"
    
    @property
    def nombre_completo_invertido(self):
        """Formato: Nombres Apellidos (como se pide en los reportes)"""
        return f"{self.nombres} {self.apellidos}"

    @property
    def nombre_con_grado(self):
        """Formato: Grado Nombres Apellidos (para encabezados de reportes)"""
        grado = f"{self.grado_academico} " if self.grado_academico else ""
        return f"{grado}{self.nombres} {self.apellidos}".strip()


class Ciclo(db.Model):
    __tablename__ = 'ciclo'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)


class CicloCarrera(db.Model):
    __tablename__ = 'ciclo_carrera'
    id = db.Column(db.Integer, primary_key=True)
    id_ciclo = db.Column(db.Integer, db.ForeignKey('ciclo.id'), nullable=False)
    id_carrera = db.Column(db.Integer, db.ForeignKey('carrera.id'), nullable=False)


class BloqueHorario(db.Model):
    __tablename__ = 'bloque_horario'
    id = db.Column(db.Integer, primary_key=True)
    id_seccion = db.Column(db.Integer, db.ForeignKey('seccion.id'), nullable=False) # <-- CAMBIO AQUÍ
    dia = db.Column(db.Integer, nullable=False)          # 1=Lun ... 7=Dom
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    tipo = db.Column(db.Enum('clase', 'receso', name='tipo_bloque_enum'), default='clase', nullable=False)

class RestriccionDocente(db.Model):
    __tablename__ = 'restriccion_docente'
    id = db.Column(db.Integer, primary_key=True)
    id_docente = db.Column(db.Integer, db.ForeignKey('docente.id'), nullable=False)
    dia = db.Column(db.Integer, nullable=False)  # 1=Lun ... 7=Dom
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    motivo = db.Column(db.String(200))  # Opcional: "Trabajo", "Clase", etc.
    
    docente = db.relationship('Docente', backref=db.backref('restricciones', cascade='all, delete-orphan'))

class Asignacion(db.Model):
    __tablename__ = 'asignacion'
    id = db.Column(db.Integer, primary_key=True)
    id_ciclo = db.Column(db.Integer, db.ForeignKey('ciclo.id'), nullable=False)
    id_seccion = db.Column(db.Integer, db.ForeignKey('seccion.id'), nullable=False)
    id_curso = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=False)
    id_docente = db.Column(db.Integer, db.ForeignKey('docente.id'))
    id_bloque = db.Column(db.Integer, db.ForeignKey('bloque_horario.id'), nullable=False)
    modalidad = db.Column(
    db.Enum('presencial', 'virtual', 'laboratorio_escuela', 'laboratorio_radiologia', name='modalidad_enum'), 
    default='presencial')

    seccion = db.relationship('Seccion')
    curso = db.relationship('Curso')
    docente = db.relationship('Docente')
    bloque = db.relationship('BloqueHorario')