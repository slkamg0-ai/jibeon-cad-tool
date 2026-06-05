/* ============================================================
   ChartManager — Chart.js chart initialisation & updates
   ============================================================ */

class ChartManager {
    constructor() {
        this.charts = {};
        this.maxDataPoints = 60;
        this.initCharts();
    }

    getCommonOptions(title) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            plugins: {
                legend: {
                    labels: { color: '#8888aa', font: { family: 'Inter', size: 11 } }
                },
                title: {
                    display: !!title,
                    text: title || '',
                    color: '#e8e8f0',
                    font: { family: 'Inter', size: 13, weight: 600 }
                }
            },
            scales: {
                x: {
                    display: false,
                    grid: { display: false }
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { color: '#555570', font: { family: 'Inter', size: 10 } }
                }
            }
        };
    }

    initCharts() {
        // ----- CPU Cores bar chart -----
        this.charts.cpuCores = new Chart(
            document.getElementById('cpu-cores-chart').getContext('2d'),
            {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Core Usage %',
                        data: [],
                        backgroundColor: [],
                        borderRadius: 4,
                        borderSkipped: false
                    }]
                },
                options: {
                    ...this.getCommonOptions(),
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: { color: '#555570', font: { family: 'Inter', size: 9 } }
                        },
                        y: {
                            min: 0, max: 100,
                            grid: { color: 'rgba(255,255,255,0.04)' },
                            ticks: {
                                color: '#555570',
                                font: { family: 'Inter', size: 10 },
                                callback: v => v + '%'
                            }
                        }
                    }
                }
            }
        );

        // ----- Network speed line chart -----
        this.charts.network = new Chart(
            document.getElementById('network-chart').getContext('2d'),
            {
                type: 'line',
                data: {
                    labels: Array(this.maxDataPoints).fill(''),
                    datasets: [
                        {
                            label: '↓ Download',
                            data: Array(this.maxDataPoints).fill(0),
                            borderColor: '#00e5ff',
                            backgroundColor: 'rgba(0, 229, 255, 0.1)',
                            fill: true,
                            tension: 0.4,
                            borderWidth: 2,
                            pointRadius: 0
                        },
                        {
                            label: '↑ Upload',
                            data: Array(this.maxDataPoints).fill(0),
                            borderColor: '#b388ff',
                            backgroundColor: 'rgba(179, 136, 255, 0.1)',
                            fill: true,
                            tension: 0.4,
                            borderWidth: 2,
                            pointRadius: 0
                        }
                    ]
                },
                options: {
                    ...this.getCommonOptions(),
                    scales: {
                        x: { display: false },
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255,255,255,0.04)' },
                            ticks: {
                                color: '#555570',
                                font: { family: 'Inter', size: 10 },
                                callback: v => this.formatBytes(v) + '/s'
                            }
                        }
                    }
                }
            }
        );

        // ----- Disk I/O line chart -----
        this.charts.diskIO = new Chart(
            document.getElementById('disk-io-chart').getContext('2d'),
            {
                type: 'line',
                data: {
                    labels: Array(this.maxDataPoints).fill(''),
                    datasets: [
                        {
                            label: 'Read',
                            data: Array(this.maxDataPoints).fill(0),
                            borderColor: '#00e676',
                            backgroundColor: 'rgba(0, 230, 118, 0.1)',
                            fill: true,
                            tension: 0.4,
                            borderWidth: 2,
                            pointRadius: 0
                        },
                        {
                            label: 'Write',
                            data: Array(this.maxDataPoints).fill(0),
                            borderColor: '#ff9100',
                            backgroundColor: 'rgba(255, 145, 0, 0.1)',
                            fill: true,
                            tension: 0.4,
                            borderWidth: 2,
                            pointRadius: 0
                        }
                    ]
                },
                options: {
                    ...this.getCommonOptions(),
                    scales: {
                        x: { display: false },
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255,255,255,0.04)' },
                            ticks: {
                                color: '#555570',
                                font: { family: 'Inter', size: 10 },
                                callback: v => this.formatBytes(v) + '/s'
                            }
                        }
                    }
                }
            }
        );
    }

    /* ---- Update helpers ---- */

    updateCpuCores(perCore) {
        const chart = this.charts.cpuCores;
        chart.data.labels = perCore.map((_, i) => `C${i}`);
        chart.data.datasets[0].data = perCore;
        chart.data.datasets[0].backgroundColor = perCore.map(v => {
            if (v < 50) return 'rgba(0, 230, 118, 0.7)';
            if (v < 70) return 'rgba(255, 234, 0, 0.7)';
            if (v < 85) return 'rgba(255, 145, 0, 0.7)';
            return 'rgba(255, 23, 68, 0.7)';
        });
        chart.update('none');
    }

    updateNetwork(downloadSpeed, uploadSpeed) {
        const chart = this.charts.network;
        chart.data.datasets[0].data.push(downloadSpeed);
        chart.data.datasets[0].data.shift();
        chart.data.datasets[1].data.push(uploadSpeed);
        chart.data.datasets[1].data.shift();
        chart.update('none');
    }

    updateDiskIO(readSpeed, writeSpeed) {
        const chart = this.charts.diskIO;
        chart.data.datasets[0].data.push(readSpeed);
        chart.data.datasets[0].data.shift();
        chart.data.datasets[1].data.push(writeSpeed);
        chart.data.datasets[1].data.shift();
        chart.update('none');
    }

    /* ---- Utility ---- */

    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
}

window.ChartManager = ChartManager;
