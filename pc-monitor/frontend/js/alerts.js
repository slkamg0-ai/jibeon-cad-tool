class AlertManager {
    constructor() {
        this.container = document.getElementById('toast-container');
        this.cooldowns = {};
        this.cooldownMs = 30000;
        this.notificationPermission = false;
        this.requestNotificationPermission();

        this.thresholds = {
            cpu: { value: 90, label: 'CPU 사용률', unit: '%', level: 'danger' },
            memory: { value: 85, label: '메모리 사용률', unit: '%', level: 'warning' },
            disk: { value: 90, label: '디스크 사용률', unit: '%', level: 'warning' },
            gpu_temp: { value: 80, label: 'GPU 온도', unit: '°C', level: 'danger' },
            gpu_load: { value: 95, label: 'GPU 사용률', unit: '%', level: 'warning' }
        };
    }

    requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission().then(p => {
                this.notificationPermission = (p === 'granted');
            });
        } else if ('Notification' in window) {
            this.notificationPermission = (Notification.permission === 'granted');
        }
    }

    check(data) {
        if (data.cpu && data.cpu.percent >= this.thresholds.cpu.value) {
            this.trigger('cpu', data.cpu.percent);
        }
        if (data.memory && data.memory.percent >= this.thresholds.memory.value) {
            this.trigger('memory', data.memory.percent);
        }
        if (data.disk && data.disk.partitions) {
            data.disk.partitions.forEach(p => {
                if (p.percent >= this.thresholds.disk.value) {
                    this.trigger('disk', p.percent, ` (${p.device})`);
                }
            });
        }
        if (data.gpu && data.gpu.length > 0) {
            data.gpu.forEach(g => {
                if (g.temperature >= this.thresholds.gpu_temp.value) {
                    this.trigger('gpu_temp', g.temperature);
                }
                if (g.load >= this.thresholds.gpu_load.value) {
                    this.trigger('gpu_load', g.load);
                }
            });
        }
    }

    trigger(type, value, extra = '') {
        const key = type + extra;
        const now = Date.now();
        if (this.cooldowns[key] && (now - this.cooldowns[key]) < this.cooldownMs) {
            return;
        }
        this.cooldowns[key] = now;

        const threshold = this.thresholds[type];
        const message = `${threshold.label}${extra}이(가) ${value}${threshold.unit}에 도달했습니다!`;

        this.showToast(message, threshold.level);
        this.showBrowserNotification(message);
    }

    showToast(message, level = 'warning') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${level}`;

        const icons = { warning: '⚠️', danger: '🔴', info: 'ℹ️' };
        const icon = icons[level] || icons.warning;

        toast.innerHTML = `
            <div class="toast-header">
                <span class="toast-icon">${icon}</span>
                <span class="toast-title">시스템 경고</span>
                <button class="toast-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            <div class="toast-body">${message}</div>
        `;

        this.container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('toast-fade-out');
            setTimeout(() => toast.remove(), 400);
        }, 5000);
    }

    showBrowserNotification(message) {
        if (this.notificationPermission) {
            new Notification('PC Monitor 경고', {
                body: message,
                icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🖥️</text></svg>'
            });
        }
    }
}

window.AlertManager = AlertManager;
