const DATA_URL = 'data/precios.json';
let priceChart = null;

// Utility functions
const formatCLP = (price) => {
    return new Intl.NumberFormat('es-CL', {
        style: 'currency',
        currency: 'CLP',
        maximumFractionDigits: 0
    }).format(price);
};

const formatDate = (dateString) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('es-CL', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
};

const getRelativeTime = (dateString) => {
    const rtf = new Intl.RelativeTimeFormat('es', { numeric: 'auto' });
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = (date.getTime() - now.getTime()) / 1000;
    
    if (Math.abs(diffInSeconds) < 60) {
        return rtf.format(Math.round(diffInSeconds), 'second');
    }
    
    const diffInMinutes = diffInSeconds / 60;
    if (Math.abs(diffInMinutes) < 60) {
        return rtf.format(Math.round(diffInMinutes), 'minute');
    }
    
    const diffInHours = diffInMinutes / 60;
    if (Math.abs(diffInHours) < 24) {
        return rtf.format(Math.round(diffInHours), 'hour');
    }
    
    const diffInDays = diffInHours / 24;
    return rtf.format(Math.round(diffInDays), 'day');
};

const animateValue = (obj, start, end, duration) => {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const easeProgress = 1 - Math.pow(1 - progress, 4); // easeOutQuart
        const currentVal = Math.floor(easeProgress * (end - start) + start);
        
        const formatted = formatCLP(currentVal).replace('CLP', '').trim();
        obj.innerHTML = `<span class="currency">$</span>${formatted.replace('$', '').trim()}`;
        
        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            const finalFormatted = formatCLP(end).replace('CLP', '').trim();
            obj.innerHTML = `<span class="currency">$</span>${finalFormatted.replace('$', '').trim()}`;
        }
    };
    window.requestAnimationFrame(step);
};

// Main render functions
const renderDashboard = async () => {
    try {
        const response = await fetch(DATA_URL);
        if (!response.ok) {
            throw new Error(`Error HTTP: ${response.status}`);
        }
        const data = await response.json();
        
        updateSummary(data);
        renderCards(data.productos);
        renderChart(data.productos);
        renderHistoryTable(data.productos);
        
    } catch (error) {
        console.error("No se pudo cargar la data: ", error);
        document.getElementById('cards-container').innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: var(--danger); background: var(--glass-bg); border-radius: var(--border-radius-md);">
                <p>Error al cargar los datos de precios. Por favor, intente más tarde.</p>
                <p style="font-size: 0.875rem; color: var(--text-muted); margin-top: 0.5rem;">${error.message}</p>
            </div>
        `;
    }
};

const updateSummary = (data) => {
    const lastUpdateEl = document.getElementById('last-update');
    if (lastUpdateEl && data.ultima_actualizacion) {
        lastUpdateEl.textContent = `Última actualización: hace ${getRelativeTime(data.ultima_actualizacion).replace('hace ', '')}`;
    }
};

const renderCards = (productos) => {
    const container = document.getElementById('cards-container');
    container.innerHTML = '';
    
    let bestPrice = Infinity;
    let bestStoreId = null;
    
    Object.entries(productos).forEach(([id, product]) => {
        if (product.precio_actual < bestPrice) {
            bestPrice = product.precio_actual;
            bestStoreId = id;
        }
    });

    Object.entries(productos).forEach(([id, product]) => {
        const isBest = id === bestStoreId;
        const history = product.historial;
        let variationHtml = '';
        
        if (history && history.length > 1) {
            const sortedHistory = [...history].sort((a, b) => new Date(b.fecha) - new Date(a.fecha));
            const current = sortedHistory[0].precio;
            const previous = sortedHistory[1].precio;
            
            if (current < previous) {
                const diff = previous - current;
                variationHtml = `<div class="price-variation variation-down">↓ ${formatCLP(diff)}</div>`;
            } else if (current > previous) {
                const diff = current - previous;
                variationHtml = `<div class="price-variation variation-up">↑ ${formatCLP(diff)}</div>`;
            } else {
                variationHtml = `<div class="price-variation variation-none">- Sin cambio</div>`;
            }
        }
        
        const card = document.createElement('div');
        card.className = `price-card ${isBest ? 'best-price' : ''}`;
        
        card.innerHTML = `
            <div class="card-header">
                <div>
                    <div class="store-name">${product.tienda}</div>
                    <div class="product-name">${product.nombre}</div>
                </div>
                ${isBest ? '<div class="best-badge">👑 Mejor Precio</div>' : ''}
            </div>
            <div class="price-container">
                <div class="price" id="price-${id}">
                    <span class="currency">$</span>0
                </div>
                ${variationHtml}
            </div>
            <a href="${product.url}" target="_blank" class="btn-buy">Ver en tienda</a>
        `;
        
        container.appendChild(card);
        
        const priceEl = document.getElementById(`price-${id}`);
        animateValue(priceEl, 0, product.precio_actual, 1500);
    });
};

const renderChart = (productos) => {
    const ctx = document.getElementById('priceChart').getContext('2d');
    
    const colors = {
        'falabella': '#6366f1', // indigo
        'maconline': '#22d3ee'  // cyan
    };
    
    const datasets = [];
    
    Object.entries(productos).forEach(([id, product]) => {
        if (!product.historial || product.historial.length === 0) return;
        
        const sortedHistory = [...product.historial].sort((a, b) => new Date(a.fecha) - new Date(b.fecha));
        
        const data = sortedHistory.map(entry => ({
            x: new Date(entry.fecha),
            y: entry.precio
        }));
        
        datasets.push({
            label: product.tienda,
            data: data,
            borderColor: colors[id] || '#8b5cf6',
            backgroundColor: (context) => {
                const ctx = context.chart.ctx;
                const gradient = ctx.createLinearGradient(0, 0, 0, 400);
                const color = colors[id] || '#8b5cf6';
                gradient.addColorStop(0, `${color}40`);
                gradient.addColorStop(1, `${color}00`);
                return gradient;
            },
            borderWidth: 2,
            pointBackgroundColor: colors[id] || '#8b5cf6',
            pointBorderColor: '#0a0a0f',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.4
        });
    });

    if (priceChart) {
        priceChart.destroy();
    }
    
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', sans-serif";
    
    priceChart = new Chart(ctx, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        boxWidth: 8
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(10, 10, 15, 0.9)',
                    titleColor: '#f8fafc',
                    bodyColor: '#e2e8f0',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                label += formatCLP(context.parsed.y);
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day',
                        displayFormats: {
                            day: 'dd MMM',
                            hour: 'HH:mm'
                        }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                        borderColor: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                        borderColor: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        callback: function(value) {
                            return '$' + (value / 1000) + 'k';
                        }
                    }
                }
            }
        }
    });
};

const renderHistoryTable = (productos) => {
    const tbody = document.createElement('tbody');
    let allHistory = [];
    
    Object.entries(productos).forEach(([id, product]) => {
        if (!product.historial) return;
        product.historial.forEach(entry => {
            allHistory.push({
                fecha: entry.fecha,
                tienda: product.tienda,
                precio: entry.precio,
                nombre: product.nombre
            });
        });
    });
    
    allHistory.sort((a, b) => new Date(b.fecha) - new Date(a.fecha));
    
    const table = document.getElementById('historyTable');
    table.innerHTML = `
        <thead>
            <tr>
                <th>Fecha y Hora</th>
                <th>Tienda</th>
                <th>Producto</th>
                <th>Precio</th>
            </tr>
        </thead>
    `;
    
    allHistory.forEach(entry => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${formatDate(entry.fecha)}</td>
            <td><strong>${entry.tienda}</strong></td>
            <td>${entry.nombre}</td>
            <td style="font-weight: 500;">${formatCLP(entry.precio)}</td>
        `;
        tbody.appendChild(tr);
    });
    
    table.appendChild(tbody);
};

document.addEventListener('DOMContentLoaded', () => {
    renderDashboard();
    
    // Auto-refresh every 5 minutes
    setInterval(renderDashboard, 5 * 60 * 1000);
});
