/* ============================================================
   GaugeRenderer — Canvas-based circular gauge with glow
   ============================================================ */

class GaugeRenderer {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.currentValue = 0;
        this.targetValue = 0;
        this.animationId = null;

        // Options with defaults
        this.lineWidth = options.lineWidth || 14;
        this.startAngle = options.startAngle || (Math.PI * 0.75);
        this.endAngle = options.endAngle || (Math.PI * 2.25);
        this.type = options.type || 'percent'; // 'percent' or 'temperature'
        this.maxTemp = options.maxTemp || 100;

        // Handle high DPI
        this.setupHiDPI();
    }

    setupHiDPI() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.ctx.scale(dpr, dpr);
        this.width = rect.width;
        this.height = rect.height;
    }

    getColor(value) {
        if (this.type === 'temperature') {
            if (value < 50) return '#00e676';
            if (value < 65) return '#ffea00';
            if (value < 80) return '#ff9100';
            return '#ff1744';
        }
        if (value < 50) return '#00e676';
        if (value < 70) return '#ffea00';
        if (value < 85) return '#ff9100';
        return '#ff1744';
    }

    draw() {
        const ctx = this.ctx;
        const cx = this.width / 2;
        const cy = this.height / 2;
        const radius = Math.min(cx, cy) - this.lineWidth - 5;

        ctx.clearRect(0, 0, this.width, this.height);

        // Background arc
        ctx.beginPath();
        ctx.arc(cx, cy, radius, this.startAngle, this.endAngle);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
        ctx.lineWidth = this.lineWidth;
        ctx.lineCap = 'round';
        ctx.stroke();

        // Value arc
        let normalizedValue;
        if (this.type === 'temperature') {
            normalizedValue = Math.min(this.currentValue / this.maxTemp, 1);
        } else {
            normalizedValue = this.currentValue / 100;
        }
        const valueAngle = this.startAngle + (this.endAngle - this.startAngle) * normalizedValue;
        const color = this.getColor(this.currentValue);

        if (normalizedValue > 0.001) {
            ctx.beginPath();
            ctx.arc(cx, cy, radius, this.startAngle, valueAngle);
            ctx.strokeStyle = color;
            ctx.lineWidth = this.lineWidth;
            ctx.lineCap = 'round';
            // Glow effect
            ctx.shadowColor = color;
            ctx.shadowBlur = 15;
            ctx.stroke();
            ctx.shadowBlur = 0;
        }
    }

    setValue(value) {
        this.targetValue = value;
        if (!this.animationId) {
            this.animate();
        }
    }

    animate() {
        const diff = this.targetValue - this.currentValue;
        if (Math.abs(diff) < 0.1) {
            this.currentValue = this.targetValue;
            this.draw();
            this.animationId = null;
            return;
        }
        this.currentValue += diff * 0.15;
        this.draw();
        this.animationId = requestAnimationFrame(() => this.animate());
    }
}

// Export for use in app.js
window.GaugeRenderer = GaugeRenderer;
