const DIAS_NOMBRE = ['', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
let bloquesCache = [];
let asignaciones = [];
let cursoSeleccionado = null;
let asignacionEditando = null;
let seccionActual = null;

// ============================================================
// Inicialización
// ============================================================
function formatoModalidad(mod) {
    const nombres = {
        'presencial': '🏫 Presencial',
        'virtual': '💻 Virtual',
        'laboratorio_escuela': '🔬 Lab. Escuela',
        'laboratorio_radiologia': '☢️ Lab. Radiología'
    };
    return nombres[mod] || mod;
}

document.addEventListener('DOMContentLoaded', () => {
    cargarDocentes();
    cargarSecciones();
    configurarBotones();
    llenarSelectsHorario();
});

// ============================================================
// Utilidad: Generar opciones de hora cada 15 minutos
// ============================================================
function llenarSelectsHorario() {
    const selects = ['cfg-inicio', 'cfg-fin', 'receso-inicio', 'receso-fin'];

    selects.forEach(id => {
        const select = document.getElementById(id);
        if (!select) return;
        select.innerHTML = '';

        for (let h = 6; h <= 22; h++) {
            for (let m = 0; m < 60; m += 15) {
                const horaStr = String(h).padStart(2, '0');
                const minStr = String(m).padStart(2, '0');
                const valor = `${horaStr}:${minStr}`;
                select.innerHTML += `<option value="${valor}">${valor}</option>`;
            }
        }
    });

    // Valores por defecto
    document.getElementById('cfg-inicio').value = '08:00';
    document.getElementById('cfg-fin').value = '21:00';
    document.getElementById('receso-inicio').value = '12:30';
    document.getElementById('receso-fin').value = '13:30';
}

// ============================================================
// Carga de Secciones y Bloques
// ============================================================
async function cargarSecciones() {
    const secs = await fetch(`/api/horario/secciones/${cicloId}`).then(r => r.json());
    const sel = document.getElementById('sel-seccion');
    sel.innerHTML = '<option value="">-- Seleccionar sección --</option>' +
        secs.map(s => `<option value="${s.seccion_id}">${s.carrera} - Sem ${s.semestre} - Sec ${s.seccion}</option>`).join('');

    sel.onchange = () => {
        const seccionId = sel.value;
        if (seccionId) {
            seccionActual = parseInt(seccionId);
            document.getElementById('panel-seccion-activa').classList.remove('hidden');
            cargarCursos(seccionActual);
            cargarBloquesYGrilla(seccionActual);
        } else {
            seccionActual = null;
            document.getElementById('panel-seccion-activa').classList.add('hidden');
            document.getElementById('sel-curso').innerHTML = '<option value="">-- Primero selecciona una sección --</option>';
            document.getElementById('horario-body').innerHTML = '';
        }
    };
}

async function cargarBloquesYGrilla(seccionId) {
    const res = await fetch(`/api/seccion/${seccionId}/bloques`);
    bloquesCache = await res.json();

    if (bloquesCache.length === 0) {
        document.getElementById('horario-body').innerHTML =
            '<tr><td colspan="8" style="text-align:center; padding:20px; color:#7f8c8d;">' +
            'Esta sección aún no tiene una grilla configurada. Haz clic en "⚙️ Configurar grilla".' +
            '</td></tr>';
    } else {
        construirGrilla();
        cargarAsignaciones();
    }
}

// ============================================================
// Construcción de la grilla
// ============================================================
function construirGrilla() {
    const body = document.getElementById('horario-body');
    body.innerHTML = '';
    const horasUnicas = [...new Set(bloquesCache.map(b => b.hora_inicio))].sort();

    horasUnicas.forEach(h => {
        const tr = document.createElement('tr');
        const tdH = document.createElement('td');
        const ref = bloquesCache.find(b => b.hora_inicio === h);

        if (ref.tipo === 'receso') {
            tdH.textContent = `☕ ${h} - ${ref.hora_fin}`;
            tdH.className = 'hora-label receso-label';
            tr.classList.add('fila-receso');
        } else {
            tdH.textContent = `${h} - ${ref.hora_fin}`;
            tdH.className = 'hora-label';
        }
        tr.appendChild(tdH);

        for (let d = 1; d <= 7; d++) {
            const td = document.createElement('td');
            const bloque = bloquesCache.find(b => b.dia == d && b.hora_inicio === h);

            if (bloque && bloque.tipo === 'receso') {
                td.className = 'celda receso';
                td.innerHTML = `
          <span class="receso-texto">☕ Receso</span>
          <span class="btn-eliminar-receso" data-bloque-id="${bloque.id}" title="Eliminar receso">×</span>
        `;
                td.dataset.tipo = 'receso';

                // Botón eliminar receso
                td.querySelector('.btn-eliminar-receso').addEventListener('click', async e => {
                    e.stopPropagation();
                    const bloqueId = e.target.dataset.bloqueId;
                    if (confirm('¿Eliminar este receso?')) {
                        const res = await fetch(`/api/seccion/${seccionActual}/bloques/${bloqueId}`, { method: 'DELETE' });
                        if (res.ok) {
                            cargarBloquesYGrilla(seccionActual);
                        } else {
                            const err = await res.json();
                            alert(err.error || 'Error al eliminar el receso');
                        }
                    }
                });
            } else {
                td.className = 'celda';
                td.dataset.dia = d;
                td.dataset.hora = h;
                td.dataset.tipo = 'clase';
                td.addEventListener('dragover', e => { e.preventDefault(); td.classList.add('over'); });
                td.addEventListener('dragleave', () => td.classList.remove('over'));
                td.addEventListener('drop', e => manejarDrop(e, td));
                td.addEventListener('click', () => colocarCursoEnCelda(td));
            }
            tr.appendChild(td);
        }
        body.appendChild(tr);
    });
}

// ============================================================
// Asignaciones
// ============================================================
async function cargarAsignaciones() {
    if (!seccionActual) return;
    const res = await fetch(`/api/horario/datos/${cicloId}/${seccionActual}`);
    asignaciones = await res.json();
    pintar();
}

function pintar() {
    document.querySelectorAll('.celda').forEach(c => {
        // No limpiar celdas de receso
        if (c.dataset.tipo === 'receso') return;
        c.innerHTML = '';
    });

    asignaciones.forEach(a => {
        const celda = document.querySelector(`.celda[data-dia="${a.dia}"][data-hora="${a.hora_inicio}"]`);
        if (!celda) return;

        const div = document.createElement('div');
        // Mapear modalidad a clase CSS
        const claseModalidad = {
            'presencial': 'presencial',
            'virtual': 'virtual',
            'laboratorio_escuela': 'lab-escuela',
            'laboratorio_radiologia': 'lab-radiologia'
        };
        div.className = `bloque ${claseModalidad[a.modalidad] || 'presencial'}`;
        div.draggable = true;
        div.dataset.id = a.id;
        div.innerHTML = `
      <span class="btn-eliminar" title="Eliminar periodo">×</span>
      <strong>${a.curso}</strong><br>
      <small>Doc: ${a.docente || '—'}</small><br>
      <small>${formatoModalidad(a.modalidad)}</small>
    `;

        div.addEventListener('dragstart', e => {
            e.dataTransfer.setData('text/plain', String(a.id));
            e.dataTransfer.effectAllowed = 'move';
            div.classList.add('dragging');
        });
        div.addEventListener('dragend', () => div.classList.remove('dragging'));

        div.addEventListener('dblclick', e => {
            if (!e.target.classList.contains('btn-eliminar')) abrirModalDocente(a);
        });

        div.querySelector('.btn-eliminar').addEventListener('click', async e => {
            e.stopPropagation();
            if (confirm(`¿Eliminar el periodo de "${a.curso}"?`)) {
                await fetch(`/api/asignacion/${a.id}`, { method: 'DELETE' });
                cargarAsignaciones();
            }
        });

        celda.appendChild(div);
    });
}

// ============================================================
// Acciones sobre la grilla
// ============================================================
async function colocarCursoEnCelda(celda) {
    if (!cursoSeleccionado) return;

    if (celda.dataset.tipo === 'receso') {
        alert('⚠️ No se pueden asignar cursos en los recesos');
        return;
    }
    if (!seccionActual) {
        alert('Selecciona una sección primero');
        return;
    }

    const bloqueId = getBloqueId(celda.dataset.dia, celda.dataset.hora);
    if (!bloqueId) return;

    await fetch('/api/asignacion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            ciclo_id: cicloId,
            seccion_id: seccionActual,
            curso_id: cursoSeleccionado,
            bloque_id: bloqueId
        })
    });

    cursoSeleccionado = null;
    document.getElementById('btn-agregar-curso').classList.remove('activo');
    cargarAsignaciones();
}

async function manejarDrop(e, celda) {
    e.preventDefault();
    celda.classList.remove('over');

    if (celda.dataset.tipo === 'receso') {
        alert('⚠️ No se pueden asignar cursos en los recesos');
        return;
    }

    const bloqueId = getBloqueId(celda.dataset.dia, celda.dataset.hora);
    if (!bloqueId) return;

    const data = e.dataTransfer.getData('text/plain');

    // Caso: Mover un bloque existente
    if (data && !isNaN(parseInt(data))) {
        const idMovido = parseInt(data);
        const a = asignaciones.find(x => x.id === idMovido);
        if (!a || a.bloque_id === bloqueId) return;

        // 1. Validar traslape de docente
        if (a.docente_id) {
            const okDocente = await validarTraslape(a.docente_id, bloqueId, a.id);
            if (!okDocente) return;
        }

        // 2. Validar traslape de laboratorio (¡AGREGADO!)
        const okLab = await validarLaboratorio(a.modalidad, bloqueId, a.id);
        if (!okLab) return;

        await fetch(`/api/asignacion/${a.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bloque_id: bloqueId })
        });
        cargarAsignaciones();
        return;
    }

    // Caso: Colocar curso nuevo desde el botón
    if (cursoSeleccionado && seccionActual) {
        await fetch('/api/asignacion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ciclo_id: cicloId,
                seccion_id: seccionActual,
                curso_id: cursoSeleccionado,
                bloque_id: bloqueId
            })
        });
        cursoSeleccionado = null;
        document.getElementById('btn-agregar-curso').classList.remove('activo');
        cargarAsignaciones();
    }
}

function getBloqueId(dia, hora) {
    const b = bloquesCache.find(s => s.dia == dia && s.hora_inicio === hora);
    return b ? b.id : null;
}

// ============================================================
// Validación de traslape
// ============================================================
async function validarTraslape(docenteId, bloqueId, asignacionId) {
    const r = await fetch('/api/validar_traslape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            docente_id: docenteId,
            bloque_id: bloqueId,
            asignacion_id: asignacionId,
            ciclo_id: cicloId
        })
    });
    const j = await r.json();
    if (j.conflicto) {
        alert('⚠️ TRASLAPE: ' + j.mensaje);
        return false;
    }
    return true;
}

async function validarLaboratorio(modalidad, bloqueId, asignacionId) {
    console.log("-> Ejecutando validarLaboratorio:", { modalidad, bloqueId, asignacionId, cicloId });

    if (modalidad !== 'laboratorio_escuela' && modalidad !== 'laboratorio_radiologia') {
        return true;
    }

    const r = await fetch('/api/validar_laboratorio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            modalidad,
            bloque_id: bloqueId,
            asignacion_id: asignacionId,
            ciclo_id: cicloId
        })
    });
    const j = await r.json();

    if (j.conflicto) {
        alert('⚠️ TRASLAPE DE LABORATORIO: ' + j.mensaje);
        return false;
    }
    return true;
}

// ============================================================
// Modal de docente
// ============================================================
function abrirModalDocente(a) {
    asignacionEditando = a;
    document.getElementById('modal-docente').classList.remove('hidden');
    document.getElementById('sel-docente').value = a.docente_id || '';
    document.getElementById('sel-modalidad').value = a.modalidad;
    document.getElementById('info-curso').textContent =
        `${a.curso} — ${a.dia ? DIAS_NOMBRE[a.dia] : ''} ${a.hora_inicio}-${a.hora_fin}`;
}

document.getElementById('btn-cancelar-docente').onclick = () => {
    document.getElementById('modal-docente').classList.add('hidden');
};

document.getElementById('btn-confirmar-docente').onclick = async () => {
    const docenteId = parseInt(document.getElementById('sel-docente').value) || null;
    const modalidad = document.getElementById('sel-modalidad').value;

    // 1. Validar traslape de docente (si hay docente)
    if (docenteId) {
        const okDocente = await validarTraslape(
            docenteId, asignacionEditando.bloque_id, asignacionEditando.id
        );
        if (!okDocente) return;
    }

    // 2. Validar traslape de laboratorio (si es un laboratorio)
    const okLab = await validarLaboratorio(
        modalidad, asignacionEditando.bloque_id, asignacionEditando.id
    );
    if (!okLab) return;

    // 3. Actualizar la asignación base
    await fetch(`/api/asignacion/${asignacionEditando.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ docente_id: docenteId, modalidad })
    });

    // 4. Propagar docente si corresponde
    if (docenteId) {
        const response = await fetch(`/api/asignacion/${asignacionEditando.id}/propagar-docente`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ docente_id: docenteId })
        });

        if (response.ok) {
            const result = await response.json();
            if (result.actualizadas > 0) {
                alert(`✅ Docente asignado a los ${result.total} periodos del curso "${asignacionEditando.curso}".`);
            }
        } else {
            // Revertir si hubo error
            await fetch(`/api/asignacion/${asignacionEditando.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ docente_id: null })
            });
            const err = await response.json();
            alert('⚠️ ' + err.error);
        }
    }

    document.getElementById('modal-docente').classList.add('hidden');
    cargarAsignaciones();
};

document.getElementById('btn-eliminar-modal').onclick = async () => {
    if (!asignacionEditando) return;
    if (confirm(`¿Eliminar el periodo de "${asignacionEditando.curso}"?`)) {
        await fetch(`/api/asignacion/${asignacionEditando.id}`, { method: 'DELETE' });
        document.getElementById('modal-docente').classList.add('hidden');
        cargarAsignaciones();
    }
};

// ============================================================
// Carga de datos auxiliares
// ============================================================
async function cargarDocentes() {
    const ds = await fetch('/api/docentes').then(r => r.json());
    const sel = document.getElementById('sel-docente');
    sel.innerHTML = '<option value="">— Sin asignar —</option>' +
        ds.map(d => `<option value="${d.id}">${d.nombre}</option>`).join('');
}

async function cargarCursos(seccionId) {
    const sel = document.getElementById('sel-curso');
    if (!seccionId) {
        sel.innerHTML = '<option value="">-- Primero selecciona una sección --</option>';
        return;
    }
    const cs = await fetch(`/api/horario/cursos/${seccionId}`).then(r => r.json());
    sel.innerHTML = '<option value="">-- Seleccionar curso --</option>' +
        cs.map(c => `<option value="${c.id}">${c.nombre} (${c.periodos}h/sem)</option>`).join('');
}

// ============================================================
// Botones del panel
// ============================================================
function configurarBotones() {
    // Botón agregar curso
    document.getElementById('btn-agregar-curso').onclick = () => {
        const sel = document.getElementById('sel-curso');
        if (!sel.value || !seccionActual) {
            alert('Selecciona una sección y un curso primero');
            return;
        }
        cursoSeleccionado = parseInt(sel.value);
        const btn = document.getElementById('btn-agregar-curso');
        btn.classList.add('activo');
        btn.textContent = '✓ Haz clic o arrastra a una celda...';
        setTimeout(() => { btn.textContent = '+ Agregar al horario'; }, 3000);
    };

    // Activar carreras
    document.getElementById('btn-activar-carreras').onclick = async () => {
        const carreras = await fetch('/api/carreras').then(r => r.json());
        const seleccion = prompt(
            'IDs de carreras activas (separados por coma):\n\n' +
            carreras.map(c => `${c.id}: ${c.nombre}`).join('\n')
        );
        if (!seleccion) return;
        const ids = seleccion.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
        await fetch(`/api/ciclo/${cicloId}/carreras`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ carreras: ids })
        });
        location.reload();
    };

    // ---------------------------------------------------------
    // Configurar grilla de bloques de clase (con recesos)
    // ---------------------------------------------------------
    document.getElementById('btn-configurar-grilla').onclick = () => {
        const sel = document.getElementById('sel-seccion');
        document.getElementById('nombre-seccion-config').textContent =
            sel.options[sel.selectedIndex].text;
        document.getElementById('config-bloques').classList.remove('hidden');
        // Limpiar lista de recesos al abrir
        document.getElementById('lista-recesos').innerHTML = '';
    };
    document.getElementById('btn-cancelar-bloques').onclick = () => {
        document.getElementById('config-bloques').classList.add('hidden');
    };
    document.getElementById('cfg-duracion').onchange = e => {
        document.getElementById('cfg-duracion-custom').classList.toggle(
            'hidden', e.target.value !== 'custom'
        );
    };

    // Agregar campo de receso al formulario
    let contadorRecesos = 0;
    document.getElementById('btn-agregar-receso-form').onclick = () => {
        contadorRecesos++;
        const div = document.createElement('div');
        div.className = 'receso-item';
        div.innerHTML = `
      <label>Hora inicio: <select class="receso-inicio"></select></label>
      <label>Hora fin: <select class="receso-fin"></select></label>
      <button type="button" class="btn-eliminar-receso-form">×</button>
    `;
        document.getElementById('lista-recesos').appendChild(div);

        // Llenar selects de este receso
        const selInicio = div.querySelector('.receso-inicio');
        const selFin = div.querySelector('.receso-fin');
        for (let h = 6; h <= 22; h++) {
            for (let m = 0; m < 60; m += 15) {
                const horaStr = String(h).padStart(2, '0');
                const minStr = String(m).padStart(2, '0');
                const valor = `${horaStr}:${minStr}`;
                selInicio.innerHTML += `<option value="${valor}">${valor}</option>`;
                selFin.innerHTML += `<option value="${valor}">${valor}</option>`;
            }
        }
        // Valores por defecto
        selInicio.value = '12:00';
        selFin.value = '13:00';

        // Botón eliminar
        div.querySelector('.btn-eliminar-receso-form').onclick = () => {
            div.remove();
        };
    };

    // Confirmar generación de bloques
    document.getElementById('btn-confirmar-bloques').onclick = async () => {
        let duracion = document.getElementById('cfg-duracion').value;
        if (duracion === 'custom') {
            duracion = parseInt(document.getElementById('cfg-duracion-custom').value);
            if (!duracion || duracion < 30) {
                alert('Duración inválida. Debe ser al menos 30 minutos.');
                return;
            }
        }

        const dias = [...document.querySelectorAll('#config-bloques input[type=checkbox][value]')]
            .filter(cb => ['1', '2', '3', '4', '5', '6', '7'].includes(cb.value) && cb.checked)
            .map(cb => parseInt(cb.value));

        if (dias.length === 0) {
            alert('Selecciona al menos un día');
            return;
        }

        // Recopilar recesos
        const recesos = [];
        document.querySelectorAll('.receso-item').forEach(item => {
            const inicio = item.querySelector('.receso-inicio').value;
            const fin = item.querySelector('.receso-fin').value;
            if (inicio && fin) {
                recesos.push({ hora_inicio: inicio, hora_fin: fin });
            }
        });

        const response = await fetch(`/api/seccion/${seccionActual}/bloques/generar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                hora_inicio: document.getElementById('cfg-inicio').value,
                hora_fin: document.getElementById('cfg-fin').value,
                duracion_min: parseInt(duracion),
                dias,
                recesos
            })
        });

        if (response.ok) {
            document.getElementById('config-bloques').classList.add('hidden');
            cargarBloquesYGrilla(seccionActual);
        } else {
            alert('Error al generar los bloques');
        }
    };
}