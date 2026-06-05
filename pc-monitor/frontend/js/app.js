class PCMonitorApp {
    constructor() {
        this.ws = null;
        this.gauges = {};
        this.chartManager = null;
        this.alertManager = null;
        this.sortBy = 'cpu';
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 10000;
        this.gpuCards = {};  // Track dynamically created GPU gauge cards
        this.gpuInitialized = false;

        this.init();
    }

    init() {
        // Initialize gauges (CPU + Memory only; GPU gauges created dynamically)
        this.gauges.cpu = new GaugeRenderer('cpu-gauge-canvas');
        this.gauges.memory = new GaugeRenderer('memory-gauge-canvas');

        // Initialize charts
        this.chartManager = new ChartManager();

        // Initialize alerts
        this.alertManager = new AlertManager();

        // Sort buttons
        document.getElementById('sort-cpu-btn').addEventListener('click', () => this.setSort('cpu'));
        document.getElementById('sort-mem-btn').addEventListener('click', () => this.setSort('memory'));

        // Connect WebSocket
        this.connect();
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);
        this.setStatus('connecting');

        this.ws.onopen = () => {
            this.setStatus('connected');
            this.reconnectDelay = 1000;
            console.log('WebSocket connected');
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.updateDashboard(data);
            } catch (e) {
                console.error('Parse error:', e);
            }
        };

        this.ws.onclose = () => {
            this.setStatus('disconnected');
            console.log(`WebSocket closed. Reconnecting in ${this.reconnectDelay / 1000}s...`);
            setTimeout(() => this.connect(), this.reconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay);
        };

        this.ws.onerror = (err) => {
            console.error('WebSocket error:', err);
        };
    }

    setStatus(status) {
        const dot = document.getElementById('status-dot');
        const text = document.getElementById('status-text');

        dot.className = 'status-dot ' + status;
        const labels = {
            connected: '실시간 연결됨',
            connecting: '연결 중...',
            disconnected: '연결 끊김'
        };
        text.textContent = labels[status] || status;
    }

    setSort(sortBy) {
        this.sortBy = sortBy;
        document.getElementById('sort-cpu-btn').classList.toggle('active', sortBy === 'cpu');
        document.getElementById('sort-mem-btn').classList.toggle('active', sortBy === 'memory');

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ sort_by: sortBy }));
        }
    }

    updateDashboard(data) {
        this.updateCPU(data.cpu);
        this.updateMemory(data.memory);
        this.updateGPU(data.gpu);
        this.updateDisk(data.disk);
        this.updateNetwork(data.network);
        this.updateProcesses(data.processes);
        this.updateSystemInfo(data.system);

        // Check alerts
        this.alertManager.check(data);
    }

    updateCPU(cpu) {
        if (!cpu) return;

        this.gauges.cpu.setValue(cpu.percent);
        document.getElementById('cpu-percent').textContent = cpu.percent.toFixed(1) + '%';
        document.getElementById('cpu-detail').textContent =
            `${cpu.cores_physical}C/${cpu.cores_logical}T · ${cpu.freq_current} MHz`;

        this.chartManager.updateCpuCores(cpu.per_core);
    }

    updateMemory(mem) {
        if (!mem) return;

        this.gauges.memory.setValue(mem.percent);
        document.getElementById('memory-percent').textContent = mem.percent.toFixed(1) + '%';
        document.getElementById('memory-detail').textContent =
            `${this.formatBytes(mem.used)} / ${this.formatBytes(mem.total)}`;
    }

    updateGPU(gpus) {
        if (!gpus || gpus.length === 0) {
            // Remove existing GPU cards if GPUs disappeared
            Object.values(this.gpuCards).forEach(card => {
                card.loadEl.parentElement.remove();
                card.tempEl.parentElement.remove();
            });
            this.gpuCards = {};
            this.gpuInitialized = false;
            return;
        }

        // Create GPU gauge cards dynamically on first data
        if (!this.gpuInitialized || Object.keys(this.gpuCards).length !== gpus.length) {
            // Remove old cards
            Object.values(this.gpuCards).forEach(card => {
                card.loadCard.remove();
                card.tempCard.remove();
            });
            this.gpuCards = {};

            const grid = document.querySelector('.gauges-grid');

            gpus.forEach((gpu, i) => {
                const gpuNum = gpus.length > 1 ? ` ${i}` : '';

                // --- Load gauge card ---
                const loadCard = document.createElement('div');
                loadCard.className = 'card gauge-card';
                loadCard.id = `gpu-load-card-${i}`;
                loadCard.innerHTML = `
                    <h3 class="gauge-title">GPU${gpuNum}</h3>
                    <div class="gauge-canvas-container">
                        <canvas id="gpu-load-canvas-${i}" width="200" height="200"></canvas>
                        <span id="gpu-percent-${i}" class="gauge-center-text">0%</span>
                    </div>
                    <p id="gpu-detail-${i}" class="gauge-detail">--</p>
                `;
                grid.appendChild(loadCard);

                // --- Temp gauge card ---
                const tempCard = document.createElement('div');
                tempCard.className = 'card gauge-card';
                tempCard.id = `gpu-temp-card-${i}`;
                tempCard.innerHTML = `
                    <h3 class="gauge-title">GPU${gpuNum} Temp</h3>
                    <div class="gauge-canvas-container">
                        <canvas id="gpu-temp-canvas-${i}" width="200" height="200"></canvas>
                        <span id="gpu-temp-value-${i}" class="gauge-center-text">0°C</span>
                    </div>
                    <p id="gpu-temp-detail-${i}" class="gauge-detail">GPU 온도</p>
                `;
                grid.appendChild(tempCard);

                // Create gauge renderers
                const loadGauge = new GaugeRenderer(`gpu-load-canvas-${i}`);
                const tempGauge = new GaugeRenderer(`gpu-temp-canvas-${i}`, { type: 'temperature', maxTemp: 100 });

                this.gpuCards[i] = {
                    loadCard, tempCard,
                    loadGauge, tempGauge
                };
            });

            this.gpuInitialized = true;
        }

        // Update all GPU gauges
        gpus.forEach((gpu, i) => {
            const card = this.gpuCards[i];
            if (!card) return;

            card.loadGauge.setValue(gpu.load);
            document.getElementById(`gpu-percent-${i}`).textContent = gpu.load.toFixed(1) + '%';
            document.getElementById(`gpu-detail-${i}`).textContent =
                `${gpu.name} · ${gpu.memory_used}/${gpu.memory_total} MB`;

            card.tempGauge.setValue(gpu.temperature || 0);
            document.getElementById(`gpu-temp-value-${i}`).textContent = (gpu.temperature || 0) + '°C';
        });
    }

    updateDisk(disk) {
        if (!disk) return;

        const container = document.getElementById('disk-partitions');
        container.innerHTML = disk.partitions.map(p => `
            <div class="disk-partition">
                <div class="disk-partition-header">
                    <span class="disk-device">${p.device}</span>
                    <span class="disk-usage">${this.formatBytes(p.used)} / ${this.formatBytes(p.total)} (${p.percent}%)</span>
                </div>
                <div class="disk-bar-container">
                    <div class="disk-bar" style="width: ${p.percent}%; background: ${this.getBarGradient(p.percent)}"></div>
                </div>
            </div>
        `).join('');

        this.chartManager.updateDiskIO(disk.io.read_speed, disk.io.write_speed);
    }

    updateNetwork(net) {
        if (!net) return;
        this.chartManager.updateNetwork(net.download_speed, net.upload_speed);

        const dlEl = document.getElementById('net-download');
        const ulEl = document.getElementById('net-upload');
        const connEl = document.getElementById('net-connections');
        if (dlEl) dlEl.textContent = this.formatBytes(net.download_speed) + '/s';
        if (ulEl) ulEl.textContent = this.formatBytes(net.upload_speed) + '/s';
        if (connEl) connEl.textContent = net.connections >= 0 ? net.connections : 'N/A';
    }

    updateProcesses(processes) {
        if (!processes) return;

        const tbody = document.getElementById('process-table-body');
        tbody.innerHTML = processes.map((p, i) => `
            <tr>
                <td class="process-rank">${i + 1}</td>
                <td class="process-pid">${p.pid}</td>
                <td class="process-name">${this.escapeHtml(p.name)}</td>
                <td class="process-cpu">
                    <span class="metric-bar">
                        <span class="metric-fill" style="width: ${Math.min(p.cpu_percent, 100)}%; background: ${this.getBarGradient(p.cpu_percent)}"></span>
                    </span>
                    ${p.cpu_percent.toFixed(1)}%
                </td>
                <td class="process-mem">
                    <span class="metric-bar">
                        <span class="metric-fill" style="width: ${Math.min(p.memory_percent, 100)}%; background: ${this.getBarGradient(p.memory_percent * 2)}"></span>
                    </span>
                    ${p.memory_percent.toFixed(1)}%
                </td>
                <td class="process-status"><span class="status-badge status-${p.status}">${p.status}</span></td>
            </tr>
        `).join('');
    }

    updateSystemInfo(sys) {
        if (!sys) return;

        document.getElementById('uptime').textContent = sys.uptime;

        const container = document.getElementById('system-info');
        container.innerHTML = [
            { icon: '💻', label: 'OS', value: sys.os },
            { icon: '🏠', label: '호스트', value: sys.hostname },
            { icon: '👤', label: '사용자', value: sys.username },
            { icon: '🕐', label: '부팅 시간', value: sys.boot_time },
            { icon: '⚙️', label: '아키텍처', value: sys.architecture },
            { icon: '🔧', label: '프로세서', value: sys.processor || 'N/A' },
            { icon: '🐍', label: 'Python', value: sys.python_version },
            { icon: '⏱️', label: '가동 시간', value: sys.uptime }
        ].map(item => `
            <div class="info-card">
                <span class="info-icon">${item.icon}</span>
                <span class="info-label">${item.label}</span>
                <span class="info-value" title="${this.escapeHtml(item.value)}">${this.escapeHtml(item.value)}</span>
            </div>
        `).join('');
    }

    formatBytes(bytes) {
        if (bytes === 0 || bytes === undefined) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[Math.min(i, sizes.length - 1)];
    }

    getBarGradient(percent) {
        if (percent < 50) return 'linear-gradient(90deg, #00e676, #69f0ae)';
        if (percent < 70) return 'linear-gradient(90deg, #ffea00, #ffd600)';
        if (percent < 85) return 'linear-gradient(90deg, #ff9100, #ff6d00)';
        return 'linear-gradient(90deg, #ff1744, #d50000)';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
}

// Start app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new PCMonitorApp();
});
