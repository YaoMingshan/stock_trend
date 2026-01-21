/**
 * A股趋势分析 - 前端脚本
 * 负责数据加载、渲染和交互
 */

class StockAnalyzer {
    constructor() {
        this.data = null;
        this.currentPeriod = '5d';
        this.dataPath = 'data/latest.json';
        this.init();
    }

    /**
     * 初始化应用
     */
    async init() {
        this.showLoading();
        await this.loadData();
        this.bindEvents();
        this.render();
        this.initBackToTop();
    }

    /**
     * 显示加载状态
     */
    showLoading() {
        const containers = ['marketOverview', 'gainersList', 'losersList', 'statisticsContent'];
        containers.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.innerHTML = '<div class="loading">数据加载中...</div>';
            }
        });
    }

    /**
     * 加载数据
     */
    async loadData() {
        try {
            // 添加时间戳防止缓存
            const timestamp = new Date().getTime();
            const response = await fetch(`${this.dataPath}?t=${timestamp}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            this.data = await response.json();
            console.log('✅ 数据加载成功:', this.data);
            
        } catch (error) {
            console.error('❌ 数据加载失败:', error);
            this.showError('数据加载失败，请稍后刷新重试');
        }
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        // Tab切换事件
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                // 更新激活状态
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');
                
                // 更新当前周期
                this.currentPeriod = e.currentTarget.dataset.period;
                
                // 重新渲染
                this.renderRankings();
                this.renderStatistics();
                this.updatePeriodBadges();
            });
        });
    }

    /**
     * 渲染所有内容
     */
    render() {
        if (!this.data) {
            this.showError('暂无数据');
            return;
        }
        
        this.renderUpdateTime();
        this.renderMarketOverview();
        this.renderRankings();
        this.renderStatistics();
        this.updatePeriodBadges();
    }

    /**
     * 渲染更新时间
     */
    renderUpdateTime() {
        const el = document.getElementById('updateTime');
        if (el && this.data.update_time) {
            el.textContent = this.data.update_time;
        }
    }

    /**
     * 渲染市场概况
     */
    renderMarketOverview() {
        const container = document.getElementById('marketOverview');
        if (!container) return;

        const overview = this.data.market_overview;
        
        if (!overview) {
            container.innerHTML = '<div class="empty">暂无市场数据</div>';
            return;
        }

        const items = [
            { label: '股票总数', value: overview.total_stocks, class: 'neutral' },
            { label: '上涨家数', value: overview.up_stocks, class: 'up' },
            { label: '下跌家数', value: overview.down_stocks, class: 'down' },
            { label: '涨停', value: overview.limit_up, class: 'up' },
            { label: '跌停', value: overview.limit_down, class: 'down' },
            { 
                label: '平均涨跌', 
                value: `${overview.avg_change >= 0 ? '+' : ''}${overview.avg_change}%`,
                class: overview.avg_change >= 0 ? 'up' : 'down'
            },
            { label: '成交额(亿)', value: overview.total_amount, class: 'neutral' }
        ];

        container.innerHTML = items.map(item => `
            <div class="overview-item">
                <div class="label">${item.label}</div>
                <div class="value ${item.class}">${item.value ?? '-'}</div>
            </div>
        `).join('');
    }

    /**
     * 渲染排行榜
     */
    renderRankings() {
        const gainersList = document.getElementById('gainersList');
        const losersList = document.getElementById('losersList');
        
        if (!this.data.periods || !this.data.periods[this.currentPeriod]) {
            if (gainersList) gainersList.innerHTML = '<div class="empty">暂无数据</div>';
            if (losersList) losersList.innerHTML = '<div class="empty">暂无数据</div>';
            return;
        }

        const periodData = this.data.periods[this.currentPeriod];
        
        // 渲染涨幅排行
        if (gainersList) {
            gainersList.innerHTML = this.renderRankingList(periodData.gainers, 'gainer');
        }
        
        // 渲染跌幅排行
        if (losersList) {
            losersList.innerHTML = this.renderRankingList(periodData.losers, 'loser');
        }
    }

    /**
     * 渲染排行列表
     */
    renderRankingList(stocks, type) {
        if (!stocks || stocks.length === 0) {
            return '<div class="empty">暂无数据</div>';
        }

        return stocks.map((stock, index) => {
            const rankClass = index < 3 ? `top${index + 1}` : '';
            const changePrefix = type === 'gainer' ? '+' : '';
            
            return `
                <div class="ranking-item">
                    <div class="rank ${rankClass}">${index + 1}</div>
                    <div class="stock-info">
                        <div class="stock-name">${this.escapeHtml(stock.name)}</div>
                        <div class="stock-code">
                            ${stock.symbol}
                            <span class="stock-price">¥${stock.price}</span>
                        </div>
                    </div>
                    <div class="stock-change">${changePrefix}${stock.period_change}%</div>
                </div>
            `;
        }).join('');
    }

    /**
     * 渲染统计信息
     */
    renderStatistics() {
        const container = document.getElementById('statisticsContent');
        if (!container) return;

        const periodData = this.data.periods?.[this.currentPeriod];
        const stats = periodData?.statistics;
        
        if (!stats) {
            container.innerHTML = '<div class="empty">暂无统计数据</div>';
            return;
        }

        const periodLabel = this.getPeriodLabel(this.currentPeriod);
        
        const items = [
            { label: '分析周期', value: periodLabel, class: '' },
            { label: '样本数量', value: stats.sample_size || stats.total_stocks || '-', class: '' },
            { 
                label: '平均涨跌幅', 
                value: `${stats.avg_change >= 0 ? '+' : ''}${stats.avg_change}%`,
                class: stats.avg_change >= 0 ? 'up' : 'down'
            },
            { label: '上涨比例', value: `${stats.up_ratio || '-'}%`, class: '' }
        ];

        container.innerHTML = `
            <div class="stats-grid">
                ${items.map(item => `
                    <div class="stat-item">
                        <div class="label">${item.label}</div>
                        <div class="value ${item.class}">${item.value}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    /**
     * 更新周期徽章
     */
    updatePeriodBadges() {
        const label = this.getPeriodLabel(this.currentPeriod);
        
        const gainersBadge = document.getElementById('gainersPeriod');
        const losersBadge = document.getElementById('losersPeriod');
        
        if (gainersBadge) gainersBadge.textContent = label;
        if (losersBadge) losersBadge.textContent = label;
    }

    /**
     * 获取周期标签
     */
    getPeriodLabel(period) {
        const labels = {
            '5d': '5日',
            '10d': '10日',
            '20d': '20日'
        };
        return labels[period] || period;
    }

    /**
     * 显示错误信息
     */
    showError(message) {
        const containers = ['marketOverview', 'gainersList', 'losersList', 'statisticsContent'];
        containers.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.innerHTML = `
                    <div class="error">
                        <div class="error-icon">⚠️</div>
                        <div>${message}</div>
                    </div>
                `;
            }
        });
    }

    /**
     * HTML转义防止XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 初始化返回顶部按钮
     */
    initBackToTop() {
        const btn = document.getElementById('backToTop');
        if (!btn) return;

        // 监听滚动
        window.addEventListener('scroll', () => {
            if (window.scrollY > 300) {
                btn.classList.add('visible');
            } else {
                btn.classList.remove('visible');
            }
        });

        // 点击返回顶部
        btn.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
}

/**
 * 工具函数：格式化数字
 */
function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    if (num >= 100000000) {
        return (num / 100000000).toFixed(2) + '亿';
    }
    if (num >= 10000) {
        return (num / 10000).toFixed(2) + '万';
    }
    return num.toLocaleString();
}

/**
 * 工具函数：格式化日期
 */
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
}

// ================================
// 页面加载完成后初始化
// ================================
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 A股趋势分析系统启动');
    window.stockAnalyzer = new StockAnalyzer();
});

// 处理页面可见性变化（用户切换回页面时刷新数据）
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && window.stockAnalyzer) {
        // 检查数据是否过期（超过1小时）
        const lastUpdate = window.stockAnalyzer.data?.update_time;
        if (lastUpdate) {
            const updateTime = new Date(lastUpdate.replace(/-/g, '/')).getTime();
            const now = new Date().getTime();
            const oneHour = 60 * 60 * 1000;
            
            if (now - updateTime > oneHour) {
                console.log('🔄 数据已过期，重新加载...');
                window.stockAnalyzer.loadData().then(() => {
                    window.stockAnalyzer.render();
                });
            }
        }
    }
});