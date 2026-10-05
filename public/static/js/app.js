/**
 * Frontend JavaScript for Vehicle Mileage Tracking Application
 * Handles reactive state, camera photo captures, previews, modals, and report exports.
 */

let currentActiveTrip = null;
let durationTimerInterval = null;
let searchDebounceTimeout = null;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    setDefaultStartTime();
    checkActiveTrip();
    loadTrips();

    // Form Submit Event Listeners
    document.getElementById('startTripForm').addEventListener('submit', handleStartTripSubmit);
    document.getElementById('stopForm').addEventListener('submit', handleStopSubmit);
    document.getElementById('finishForm').addEventListener('submit', handleFinishSubmit);
});

// Helper: Sets current local time in datetime-local input
function setDefaultStartTime() {
    const input = document.getElementById('startTimeInput');
    if (input) {
        const now = new Date();
        const offset = now.getTimezoneOffset() * 60000;
        const localISOTime = (new Date(now.getTime() - offset)).toISOString().slice(0, 16);
        input.value = localISOTime;
    }
}

// -------------------------------------------------------------
// Photo Upload & Preview Helpers
// -------------------------------------------------------------

function handlePhotoSelect(input, previewId, boxContentId) {
    if (!input.files || !input.files[0]) return;

    const file = input.files[0];
    if (file.size > 16 * 1024 * 1024) {
        showToast('A imagem selecionada é muito grande (máximo 16MB).', 'danger');
        input.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const previewContainer = document.getElementById(previewId);
        const boxContent = document.getElementById(boxContentId);
        const previewImg = previewContainer.querySelector('img');

        previewImg.src = e.target.result;
        previewContainer.classList.remove('d-none');
        boxContent.classList.add('d-none');
    };
    reader.readAsDataURL(file);
}

function clearPhotoSelection(event, inputId, previewId, boxContentId) {
    event.stopPropagation();
    const input = document.getElementById(inputId);
    const previewContainer = document.getElementById(previewId);
    const boxContent = document.getElementById(boxContentId);

    input.value = '';
    previewContainer.classList.add('d-none');
    boxContent.classList.remove('d-none');
}

// -------------------------------------------------------------
// Active Trip Logic
// -------------------------------------------------------------

async function checkActiveTrip() {
    try {
        const res = await fetch('/api/active-trip');
        const data = await res.json();

        const activeContainer = document.getElementById('activeTripContainer');
        const newTripContainer = document.getElementById('newTripContainer');
        const navBadge = document.getElementById('navStatusBadge');

        if (data.success && data.trip) {
            currentActiveTrip = data.trip;

            // Update Navbar badge
            navBadge.className = 'badge bg-warning text-dark pulse-badge';
            navBadge.innerHTML = `<i class="bi bi-broadcast me-1"></i> Em Viagem (${currentActiveTrip.vehicle_plate})`;

            // Populate Active Trip Card
            document.getElementById('activePlate').textContent = currentActiveTrip.vehicle_plate;
            document.getElementById('activeDriver').textContent = [currentActiveTrip.origin_city, currentActiveTrip.origin_br ? 'BR-' + currentActiveTrip.origin_br : ''].filter(Boolean).join(' / ') || '-';
            document.getElementById('activeModel').textContent = currentActiveTrip.action_type || '-';
            document.getElementById('activeStartTime').textContent = formatDateTime(currentActiveTrip.start_time);
            document.getElementById('activeStartKm').textContent = `${formatNumber(currentActiveTrip.start_km)} KM`;
            document.getElementById('activePurpose').textContent = currentActiveTrip.purpose || 'Sem observações.';

            // Photo thumb
            const thumb = document.getElementById('activeStartPhotoThumb');
            thumb.src = `/uploads/${currentActiveTrip.start_photo}`;

            // Populate Stops
            renderActiveStops(currentActiveTrip.stops || []);

            // Start Live Duration Timer
            startDurationTimer(currentActiveTrip.start_time);

            activeContainer.classList.remove('d-none');
            newTripContainer.classList.add('d-none');
        } else {
            currentActiveTrip = null;
            clearInterval(durationTimerInterval);

            navBadge.className = 'badge bg-secondary';
            navBadge.innerHTML = '<i class="bi bi-check-circle me-1"></i> Pronto para Nova Viagem';

            activeContainer.classList.add('d-none');
            newTripContainer.classList.remove('d-none');
            setDefaultStartTime();
        }
    } catch (err) {
        console.error('Erro ao verificar viagem ativa:', err);
    }
}

function renderActiveStops(stops) {
    const stopsCountEl = document.getElementById('activeStopsCount');
    const noStopsMsg = document.getElementById('noStopsMsg');
    const stopsItems = document.getElementById('activeStopsItems');

    stopsCountEl.textContent = stops.length;
    stopsItems.innerHTML = '';

    if (stops.length === 0) {
        noStopsMsg.classList.remove('d-none');
    } else {
        noStopsMsg.classList.add('d-none');
        stops.forEach((s, idx) => {
            const div = document.createElement('div');
            div.className = 'd-flex align-items-center justify-content-between bg-white bg-opacity-10 rounded p-2 text-white small';
            div.innerHTML = `
                <div class="d-flex align-items-center gap-2">
                    <span class="badge bg-warning text-dark">${idx + 1}ª Parada</span>
                    <strong class="text-warning">${formatNumber(s.stop_km)} KM</strong>
                    <span class="text-white-50">(${formatTimeOnly(s.stop_time)})</span>
                    <span>${s.reason ? '&bull; ' + escapeHtml(s.reason) : ''}</span>
                </div>
                <div>
                    <img src="/uploads/${s.photo}" class="odometer-thumb" style="width: 36px; height: 36px;" onclick="viewPhoto(this.src, 'Foto da Parada #${idx + 1}')" title="Ver Foto">
                </div>
            `;
            stopsItems.appendChild(div);
        });
    }
}

function startDurationTimer(startTimeStr) {
    clearInterval(durationTimerInterval);
    const durationEl = document.getElementById('activeDuration');

    function update() {
        const start = new Date(startTimeStr.replace(' ', 'T')).getTime();
        const now = new Date().getTime();
        const diffMs = Math.max(0, now - start);

        const hours = Math.floor(diffMs / (1000 * 60 * 60));
        const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
        durationEl.textContent = `${hours}h ${minutes}m`;
    }

    update();
    durationTimerInterval = setInterval(update, 30000); // Update every 30s
}

// -------------------------------------------------------------
// Start Trip (Saída)
// -------------------------------------------------------------

async function handleStartTripSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById('btnStartSubmit');

    const photoInput = document.getElementById('startPhotoInput');
    if (!photoInput.files || !photoInput.files[0]) {
        showToast('Tire ou selecione uma foto do odômetro.', 'warning');
        return;
    }

    const formData = new FormData(form);

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Carimbando imagem e salvando...';

    try {
        const res = await fetch('/api/trips/start', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message, 'success');
            form.reset();
            clearPhotoSelection(new Event('clear'), 'startPhotoInput', 'startPreview', 'startPhotoBoxContent');
            await checkActiveTrip();
            loadTrips();
        } else {
            showToast(data.error || 'Erro ao iniciar viagem.', 'danger');
        }
    } catch (err) {
        showToast('Erro de conexão ao salvar viagem.', 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-play-circle-fill me-2"></i> Iniciar Viagem';
    }
}

// -------------------------------------------------------------
// Stop (Parada)
// -------------------------------------------------------------

function openStopModal() {
    if (!currentActiveTrip) return;

    document.getElementById('modalStopStartKm').textContent = `${formatNumber(currentActiveTrip.start_km)} KM`;
    const minKm = currentActiveTrip.stops && currentActiveTrip.stops.length > 0
        ? Math.max(...currentActiveTrip.stops.map(s => s.stop_km))
        : currentActiveTrip.start_km;

    const kmInput = document.getElementById('stopKmInput');
    kmInput.min = minKm;
    kmInput.value = '';
    document.getElementById('stopReasonInput').value = '';
    clearPhotoSelection(new Event('clear'), 'stopPhotoInput', 'stopPreview', 'stopPhotoBoxContent');

    const modal = new bootstrap.Modal(document.getElementById('modalStop'));
    modal.show();
}

async function handleStopSubmit(e) {
    e.preventDefault();
    if (!currentActiveTrip) return;

    const form = e.target;
    const btn = document.getElementById('btnStopSubmit');
    const photoInput = document.getElementById('stopPhotoInput');

    if (!photoInput.files || !photoInput.files[0]) {
        showToast('Tire ou selecione a foto do odômetro na parada.', 'warning');
        return;
    }

    const formData = new FormData(form);

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Gravando parada...';

    try {
        const res = await fetch(`/api/trips/${currentActiveTrip.id}/stop`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message, 'success');
            bootstrap.Modal.getInstance(document.getElementById('modalStop')).hide();
            await checkActiveTrip();
            loadTrips();
        } else {
            showToast(data.error || 'Erro ao registrar parada.', 'danger');
        }
    } catch (err) {
        showToast('Erro de comunicação com o servidor.', 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i> Salvar Parada';
    }
}

// -------------------------------------------------------------
// Finish Trip (Chegada)
// -------------------------------------------------------------

function openFinishModal() {
    if (!currentActiveTrip) return;

    document.getElementById('modalFinishStartKm').textContent = `${formatNumber(currentActiveTrip.start_km)} KM`;

    const lastStopWrapper = document.getElementById('modalFinishLastStopWrapper');
    let minKm = currentActiveTrip.start_km;

    if (currentActiveTrip.stops && currentActiveTrip.stops.length > 0) {
        minKm = Math.max(...currentActiveTrip.stops.map(s => s.stop_km));
        document.getElementById('modalFinishLastStopKm').textContent = `${formatNumber(minKm)} KM`;
        lastStopWrapper.classList.remove('d-none');
    } else {
        lastStopWrapper.classList.add('d-none');
    }

    const kmInput = document.getElementById('finishKmInput');
    kmInput.min = minKm;
    kmInput.value = '';
    document.getElementById('distancePreviewAlert').classList.add('d-none');
    clearPhotoSelection(new Event('clear'), 'finishPhotoInput', 'finishPreview', 'finishPhotoBoxContent');

    const modal = new bootstrap.Modal(document.getElementById('modalFinish'));
    modal.show();
}

function calculateDistancePreview() {
    if (!currentActiveTrip) return;
    const endVal = parseFloat(document.getElementById('finishKmInput').value);
    const alertBox = document.getElementById('distancePreviewAlert');
    const previewEl = document.getElementById('finishDistancePreview');

    if (!isNaN(endVal) && endVal >= currentActiveTrip.start_km) {
        const dist = (endVal - currentActiveTrip.start_km).toFixed(1);
        previewEl.textContent = `${formatNumber(dist)} KM`;
        alertBox.classList.remove('d-none');
    } else {
        alertBox.classList.add('d-none');
    }
}

async function handleFinishSubmit(e) {
    e.preventDefault();
    if (!currentActiveTrip) return;

    const form = e.target;
    const btn = document.getElementById('btnFinishSubmit');
    const photoInput = document.getElementById('finishPhotoInput');

    if (!photoInput.files || !photoInput.files[0]) {
        showToast('Tire ou selecione a foto de chegada do odômetro.', 'warning');
        return;
    }

    const formData = new FormData(form);

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Encerrando viagem...';

    try {
        const res = await fetch(`/api/trips/${currentActiveTrip.id}/finish`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        if (data.success) {
            showToast(data.message, 'success');
            bootstrap.Modal.getInstance(document.getElementById('modalFinish')).hide();
            await checkActiveTrip();
            loadTrips();
        } else {
            showToast(data.error || 'Erro ao finalizar viagem.', 'danger');
        }
    } catch (err) {
        showToast('Erro de comunicação com o servidor.', 'danger');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-check2-all me-1"></i> Concluir Viagem';
    }
}

// -------------------------------------------------------------
// Cancel & Delete
// -------------------------------------------------------------

async function confirmCancelTrip() {
    if (!currentActiveTrip) return;
    const confirmed = confirm(`Tem certeza que deseja CANCELAR a viagem em andamento (${currentActiveTrip.vehicle_plate})?`);
    if (!confirmed) return;

    try {
        const res = await fetch(`/api/trips/${currentActiveTrip.id}/cancel`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'info');
            await checkActiveTrip();
            loadTrips();
        } else {
            showToast(data.error, 'danger');
        }
    } catch (err) {
        showToast('Erro ao cancelar viagem.', 'danger');
    }
}

async function deleteTrip(tripId, plate) {
    const confirmed = confirm(`Deseja realmente excluir o registro da viagem #${tripId} (${plate})? Esta ação não pode ser desfeita.`);
    if (!confirmed) return;

    try {
        const res = await fetch(`/api/trips/${tripId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast(data.message, 'success');
            await checkActiveTrip();
            loadTrips();
        } else {
            showToast(data.error, 'danger');
        }
    } catch (err) {
        showToast('Erro ao excluir viagem.', 'danger');
    }
}

// -------------------------------------------------------------
// History & Reports
// -------------------------------------------------------------

function debounceLoadTrips() {
    clearTimeout(searchDebounceTimeout);
    searchDebounceTimeout = setTimeout(loadTrips, 300);
}

async function loadTrips() {
    const monthSelect = document.getElementById('filterMonth');
    const selectedMonth = monthSelect.value;
    const status = document.getElementById('filterStatus').value;
    const search = document.getElementById('filterSearch').value;

    const params = new URLSearchParams();
    if (selectedMonth) params.append('month', selectedMonth);
    if (status) params.append('status', status);
    if (search) params.append('search', search);

    try {
        const res = await fetch(`/api/trips?${params.toString()}`);
        const data = await res.json();

        if (data.success) {
            updateMonthsFilter(data.available_months, selectedMonth);
            updateKpiStats(data.stats);
            renderTripsTable(data.trips);
        }
    } catch (err) {
        console.error('Erro ao carregar histórico:', err);
    }
}

function updateMonthsFilter(availableMonths, selectedMonth) {
    const select = document.getElementById('filterMonth');
    const currentVal = selectedMonth || select.value;

    // Preserve first option "Todos os Meses"
    select.innerHTML = '<option value="">Todos os Meses</option>';

    if (availableMonths && availableMonths.length > 0) {
        availableMonths.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            // Format YYYY-MM to MonthName/YYYY
            const [year, month] = m.split('-');
            const date = new Date(year, parseInt(month) - 1, 1);
            const monthName = date.toLocaleString('pt-BR', { month: 'long' });
            opt.textContent = `${monthName.charAt(0).toUpperCase() + monthName.slice(1)} / ${year}`;
            if (m === currentVal) opt.selected = true;
            select.appendChild(opt);
        });
    }
}

function updateKpiStats(stats) {
    if (!stats) return;
    document.getElementById('kpiTotalTrips').textContent = stats.total_trips;
    document.getElementById('kpiTotalKm').textContent = `${formatNumber(stats.total_km)} KM`;
    document.getElementById('kpiAvgKm').textContent = `${formatNumber(stats.avg_km)} KM`;
    document.getElementById('kpiVehicles').textContent = stats.unique_vehicles;
}

function renderTripsTable(trips) {
    const tbody = document.getElementById('tripsTableBody');
    const badge = document.getElementById('tableCountBadge');
    badge.textContent = `${trips.length} registro${trips.length === 1 ? '' : 's'}`;

    tbody.innerHTML = '';

    if (!trips || trips.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-5 text-muted">
                    <i class="bi bi-inbox fs-2 d-block mb-2 text-secondary"></i>
                    Nenhuma viagem encontrada com os filtros selecionados.
                </td>
            </tr>
        `;
        return;
    }

    trips.forEach(t => {
        const tr = document.createElement('tr');

        // Status Badge
        let statusBadge = '';
        if (t.status === 'FINALIZADA') {
            statusBadge = '<span class="badge bg-success-subtle text-success border border-success-subtle">Finalizada</span>';
        } else if (t.status === 'EM_ANDAMENTO') {
            statusBadge = '<span class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle">Em Andamento</span>';
        } else {
            statusBadge = '<span class="badge bg-secondary-subtle text-secondary border">Cancelada</span>';
        }

        // Stops text
        const stopsCount = (t.stops || []).length;
        const stopsBadge = stopsCount > 0
            ? `<span class="badge bg-info-subtle text-info-emphasis border border-info-subtle" title="${stopsCount} parada(s)">${stopsCount} parada${stopsCount > 1 ? 's' : ''}</span>`
            : '<span class="text-muted small">Nenhuma</span>';

        const totalKmText = t.total_km !== null
            ? `<strong class="text-primary">${formatNumber(t.total_km)} KM</strong>`
            : '<span class="text-muted">-</span>';

        tr.innerHTML = `
            <td class="ps-3">
                <span class="fw-bold text-dark">#${t.id}</span>
                <small class="d-block text-muted">${formatDateTime(t.start_time)}</small>
            </td>
            <td>
                <span class="fw-bold font-monospace text-uppercase">${escapeHtml(t.vehicle_plate)}</span>
                <small class="d-block text-muted">${escapeHtml(t.origin_city || '-')} (BR-${escapeHtml(t.origin_br || '-')}) &rarr; ${escapeHtml(t.dest_city || '-')}${t.dest_br ? ' (BR-' + escapeHtml(t.dest_br) + ')' : ''}</small>
            </td>
            <td>
                <div class="d-flex align-items-center gap-2">
                    <img src="/uploads/${t.start_photo}" class="odometer-thumb" onclick="viewPhoto(this.src, 'Odômetro de Saída #${t.id}')" title="Ver Foto Saída">
                    <span>${formatNumber(t.start_km)} KM</span>
                </div>
            </td>
            <td>${stopsBadge}</td>
            <td>
                ${t.end_photo ? `
                    <div class="d-flex align-items-center gap-2">
                        <img src="/uploads/${t.end_photo}" class="odometer-thumb" onclick="viewPhoto(this.src, 'Odômetro de Chegada #${t.id}')" title="Ver Foto Chegada">
                        <span>${formatNumber(t.end_km)} KM</span>
                    </div>
                ` : '<span class="text-muted">-</span>'}
            </td>
            <td>${totalKmText}</td>
            <td>${statusBadge}</td>
            <td class="text-end pe-3">
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-primary" onclick="viewTripDetails(${t.id})" title="Ver Detalhes">
                        <i class="bi bi-eye"></i>
                    </button>
                    <button class="btn btn-outline-danger" onclick="deleteTrip(${t.id}, '${t.vehicle_plate}')" title="Excluir">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// -------------------------------------------------------------
// Trip Details Modal (Timeline)
// -------------------------------------------------------------

async function viewTripDetails(tripId) {
    try {
        const res = await fetch(`/api/trips/${tripId}`);
        const data = await res.json();
        if (!data.success || !data.trip) return;

        const t = data.trip;
        document.getElementById('detailModalTitle').innerHTML = `
            <i class="bi bi-journal-text me-2 text-warning"></i> Viagem #${t.id} &bull; ${escapeHtml(t.vehicle_plate)}
        `;

        let timelineHtml = `
            <div class="row g-3 mb-4">
                <div class="col-sm-4">
                    <small class="text-muted d-block">Origem</small>
                    <strong class="fs-6">${escapeHtml(t.origin_city || '-')} (BR-${escapeHtml(t.origin_br || '-')})</strong>
                </div>
                <div class="col-sm-4">
                    <small class="text-muted d-block">Destino / Tipo de Ação</small>
                    <span>${escapeHtml(t.dest_city || '-')}${t.dest_br ? ' (BR-' + escapeHtml(t.dest_br) + ')' : ''} &bull; ${escapeHtml(t.action_type || '-')}</span>
                </div>
                <div class="col-sm-4">
                    <small class="text-muted d-block">Distância Total Percorrida</small>
                    <strong class="fs-5 text-success">${t.total_km ? formatNumber(t.total_km) + ' KM' : 'Em andamento'}</strong>
                </div>
                <div class="col-12">
                    <small class="text-muted d-block">Finalidade / Rota</small>
                    <div class="bg-light p-2 rounded small">${escapeHtml(t.purpose || 'Sem observações')}</div>
                </div>
            </div>

            <h6 class="fw-bold mb-3 border-bottom pb-2">Linha do Tempo e Registros Fotográficos</h6>
            <ul class="timeline">
                <!-- Saída -->
                <li class="timeline-item">
                    <div class="timeline-badge bg-primary"><i class="bi bi-play-fill"></i></div>
                    <div class="card p-3 border shadow-none bg-light">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <span class="badge bg-primary mb-1">SAÍDA</span>
                                <h6 class="fw-bold mb-0 text-dark">${formatNumber(t.start_km)} KM</h6>
                                <small class="text-muted">${formatDateTime(t.start_time)}</small>
                            </div>
                            <img src="/uploads/${t.start_photo}" class="odometer-thumb" style="width: 64px; height: 64px;" onclick="viewPhoto(this.src, 'Odômetro Saída #${t.id}')">
                        </div>
                    </div>
                </li>
        `;

        // Stops
        if (t.stops && t.stops.length > 0) {
            t.stops.forEach((s, idx) => {
                timelineHtml += `
                    <li class="timeline-item">
                        <div class="timeline-badge bg-warning"><i class="bi bi-pause-fill"></i></div>
                        <div class="card p-3 border shadow-none bg-light">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <span class="badge bg-warning text-dark mb-1">${idx + 1}ª PARADA</span>
                                    <h6 class="fw-bold mb-0 text-dark">${formatNumber(s.stop_km)} KM</h6>
                                    <small class="text-muted">${formatDateTime(s.stop_time)}</small>
                                    ${s.reason ? `<p class="mb-0 mt-1 small text-dark"><strong>Motivo:</strong> ${escapeHtml(s.reason)}</p>` : ''}
                                </div>
                                <img src="/uploads/${s.photo}" class="odometer-thumb" style="width: 64px; height: 64px;" onclick="viewPhoto(this.src, 'Odômetro Parada #${idx + 1}')">
                            </div>
                        </div>
                    </li>
                `;
            });
        }

        // Chegada (if finished)
        if (t.status === 'FINALIZADA' && t.end_km) {
            timelineHtml += `
                <li class="timeline-item">
                    <div class="timeline-badge bg-success"><i class="bi bi-flag-fill"></i></div>
                    <div class="card p-3 border shadow-none bg-light">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <span class="badge bg-success mb-1">CHEGADA (FIM)</span>
                                <h6 class="fw-bold mb-0 text-dark">${formatNumber(t.end_km)} KM</h6>
                                <small class="text-muted">${formatDateTime(t.end_time)}</small>
                                <div class="mt-2 text-success fw-bold">Total Percorrido: +${formatNumber(t.total_km)} KM</div>
                            </div>
                            <img src="/uploads/${t.end_photo}" class="odometer-thumb" style="width: 64px; height: 64px;" onclick="viewPhoto(this.src, 'Odômetro Chegada #${t.id}')">
                        </div>
                    </div>
                </li>
            `;
        }

        timelineHtml += `</ul>`;
        document.getElementById('detailModalBody').innerHTML = timelineHtml;

        const modal = new bootstrap.Modal(document.getElementById('modalTripDetails'));
        modal.show();
    } catch (err) {
        showToast('Erro ao carregar detalhes da viagem.', 'danger');
    }
}

// -------------------------------------------------------------
// Lightbox Viewer
// -------------------------------------------------------------

function viewPhoto(imgSrc, title) {
    document.getElementById('lightboxTitle').textContent = title || 'Foto do Odômetro';
    const img = document.getElementById('lightboxImg');
    img.src = imgSrc;
    const downloadBtn = document.getElementById('lightboxDownloadBtn');
    downloadBtn.href = imgSrc;
    downloadBtn.setAttribute('download', imgSrc.split('/').pop());

    const modal = new bootstrap.Modal(document.getElementById('modalLightbox'));
    modal.show();
}

// -------------------------------------------------------------
// Export Reports
// -------------------------------------------------------------

function exportData(format) {
    const month = document.getElementById('filterMonth').value;
    const status = document.getElementById('filterStatus').value;
    const search = document.getElementById('filterSearch').value;

    const params = new URLSearchParams();
    if (month) params.append('month', month);
    if (status) params.append('status', status);
    if (search) params.append('search', search);

    const url = `/api/export/${format}?${params.toString()}`;
    window.location.href = url;
}

// -------------------------------------------------------------
// Utilities
// -------------------------------------------------------------

function showToast(message, type = 'info') {
    const toastEl = document.getElementById('liveToast');
    const toastBody = document.getElementById('toastMessage');

    toastEl.className = `toast align-items-center text-white border-0 shadow bg-${type}`;
    toastBody.innerHTML = `
        <i class="bi bi-${type === 'success' ? 'check-circle-fill' : type === 'danger' ? 'exclamation-triangle-fill' : 'info-circle-fill'} fs-5"></i>
        <span>${escapeHtml(message)}</span>
    `;

    const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
    toast.show();
}

function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return '-';
    return Number(num).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

function formatDateTime(isoStr) {
    if (!isoStr) return '-';
    try {
        const clean = isoStr.replace(' ', 'T');
        const dt = new Date(clean);
        if (isNaN(dt.getTime())) return isoStr;
        return dt.toLocaleString('pt-BR', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    } catch {
        return isoStr;
    }
}

function formatTimeOnly(isoStr) {
    if (!isoStr) return '';
    try {
        const clean = isoStr.replace(' ', 'T');
        const dt = new Date(clean);
        if (isNaN(dt.getTime())) return '';
        return dt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    } catch {
        return '';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}
