/**
 * Antigravity Table Manager JS
 * 通用后台数据表格交互核心逻辑：排序、动态筛选、批量勾选/跨页全选、分页及条数切换、导出。
 */
function initAll() {
    // 初始化页面自定义下拉组件
    initCustomSelects();

    // 监听全选框与单选框联动
    initTableSelection();

    // 拦截表格筛选表单提交，确保提交时保持 #logs / #users / #keys hash 锚点
    document.querySelectorAll('.table-filter-form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const action = form.getAttribute('action');
            if (action && action.includes('#')) {
                const targetHash = action.substring(action.indexOf('#'));
                window.location.hash = targetHash;
            }
        });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
} else {
    initAll();
}

/**
 * 字段排序逻辑
 */
function handleSort(prefix, field) {
    const urlParams = new URLSearchParams(window.location.search);
    const sortKey = prefix ? `${prefix}_sort_by` : 'sort_by';
    const orderKey = prefix ? `${prefix}_order` : 'order';
    const pageKey = prefix ? `${prefix}_page` : 'page';

    const currentSort = urlParams.get(sortKey);
    const currentOrder = urlParams.get(orderKey) || 'desc';

    let nextOrder = 'asc';
    if (currentSort === field) {
        nextOrder = currentOrder.toLowerCase() === 'asc' ? 'desc' : 'asc';
    }

    urlParams.set(sortKey, field);
    urlParams.set(orderKey, nextOrder);
    urlParams.set(pageKey, '1'); // 排序重置为第 1 页

    const targetHash = prefix ? `#${prefix}` : window.location.hash;
    window.location.search = urlParams.toString();
    if (targetHash) {
        window.location.hash = targetHash;
    }
}

/**
 * 切换每页显示条数 (20, 50, 100, 200)
 */
function handlePageSizeChange(prefix, pageSize) {
    const urlParams = new URLSearchParams(window.location.search);
    const pageSizeKey = prefix ? `${prefix}_page_size` : 'page_size';
    const pageKey = prefix ? `${prefix}_page` : 'page';

    urlParams.set(pageSizeKey, pageSize);
    urlParams.set(pageKey, '1'); // 重置为第 1 页

    const targetHash = prefix ? `#${prefix}` : window.location.hash;
    window.location.search = urlParams.toString();
    if (targetHash) {
        window.location.hash = targetHash;
    }
}

/**
 * 页码跳转
 */
function handlePageChange(prefix, page) {
    const urlParams = new URLSearchParams(window.location.search);
    const pageKey = prefix ? `${prefix}_page` : 'page';

    urlParams.set(pageKey, page);

    const targetHash = prefix ? `#${prefix}` : window.location.hash;
    window.location.search = urlParams.toString();
    if (targetHash) {
        window.location.hash = targetHash;
    }
}

/**
 * 表格筛选表单提交与重置
 */
function resetTableFilter(prefix) {
    const urlParams = new URLSearchParams(window.location.search);
    const keysToRemove = [];

    urlParams.forEach((val, key) => {
        if (prefix && key.startsWith(`${prefix}_`)) {
            keysToRemove.push(key);
        } else if (!prefix && ['q', 'status_code', 'platform', 'role', 'active', 'start_date', 'end_date'].includes(key)) {
            keysToRemove.push(key);
        }
    });

    keysToRemove.forEach(key => urlParams.delete(key));

    const targetHash = prefix ? `#${prefix}` : window.location.hash;
    window.location.search = urlParams.toString();
    if (targetHash) {
        window.location.hash = targetHash;
    }
}

/**
 * 批量勾选与全选状态机联动（支持“选择当前页”和“选择全部”下拉菜单）
 */
function initTableSelection() {
    // 监听所有批量下拉菜单触发器
    document.querySelectorAll('.batch-dropdown-trigger').forEach(trigger => {
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            const parentDropdown = trigger.closest('.batch-select-dropdown');
            if (!parentDropdown) return;

            const wasOpen = parentDropdown.classList.contains('open');
            document.querySelectorAll('.batch-select-dropdown.open').forEach(dd => {
                if (dd !== parentDropdown) dd.classList.remove('open');
            });

            if (wasOpen) {
                parentDropdown.classList.remove('open');
            } else {
                parentDropdown.classList.add('open');
            }
        });
    });

    // 监听下拉菜单选项点击
    document.querySelectorAll('.batch-dropdown-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            const dropdown = item.closest('.batch-select-dropdown');
            if (!dropdown) return;

            const tableId = dropdown.getAttribute('data-table');
            const totalCount = dropdown.getAttribute('data-total') || '0';
            const action = item.getAttribute('data-action');
            const table = document.getElementById(tableId);
            const selectAllCheckbox = dropdown.querySelector('.table-select-all');

            dropdown.classList.remove('open');
            if (!table) return;

            if (action === 'current-page') {
                table.setAttribute('data-select-mode', 'page');
                table.querySelectorAll('.row-checkbox').forEach(cb => { cb.checked = true; });
                if (selectAllCheckbox) {
                    selectAllCheckbox.checked = true;
                    selectAllCheckbox.indeterminate = false;
                }
                updateSelectionState(tableId);
            } else if (action === 'all') {
                table.setAttribute('data-select-mode', 'all');
                table.setAttribute('data-total-count', totalCount);
                table.querySelectorAll('.row-checkbox').forEach(cb => { cb.checked = true; });
                if (selectAllCheckbox) {
                    selectAllCheckbox.checked = true;
                    selectAllCheckbox.indeterminate = false;
                }
                updateSelectionState(tableId);
            }
        });
    });

    // 点击外部区域自动关闭所有批量选择下拉菜单
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.batch-select-dropdown')) {
            document.querySelectorAll('.batch-select-dropdown.open').forEach(dd => {
                dd.classList.remove('open');
            });
        }
    });

    // 表头复选框与行复选框交互
    document.querySelectorAll('.table-select-all').forEach(selectAllCheckbox => {
        const tableId = selectAllCheckbox.getAttribute('data-table');
        if (!tableId) return;

        const table = document.getElementById(tableId);
        if (!table) return;

        const rowCheckboxes = table.querySelectorAll('.row-checkbox');

        // 表头总控勾选（直接点击方框）
        selectAllCheckbox.addEventListener('change', (e) => {
            const isChecked = e.target.checked;
            table.removeAttribute('data-select-mode');
            const currentRows = table.querySelectorAll('.row-checkbox');
            currentRows.forEach(cb => {
                cb.checked = isChecked;
            });
            updateSelectionState(tableId);
        });

        // 行复选框联动
        rowCheckboxes.forEach(cb => {
            cb.addEventListener('change', () => {
                table.removeAttribute('data-select-mode');
                const totalCount = table.querySelectorAll('.row-checkbox').length;
                const checkedCount = table.querySelectorAll('.row-checkbox:checked').length;
                selectAllCheckbox.checked = checkedCount === totalCount && totalCount > 0;
                selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < totalCount;
                updateSelectionState(tableId);
            });
        });
    });
}

/**
 * 更新选中数量提示条与底部悬浮胶囊工具栏
 */
function updateSelectionState(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const checkedRows = table.querySelectorAll('.row-checkbox:checked');
    const count = checkedRows.length;
    const isAllMode = table.getAttribute('data-select-mode') === 'all';
    const totalCount = table.getAttribute('data-total-count') || count;

    // 更新各选择计数值
    const countTexts = document.querySelectorAll(`.${tableId}-selected-count, #${tableId}-selected-count`);
    countTexts.forEach(el => {
        if (isAllMode) {
            el.innerText = `全部 ${totalCount}`;
        } else {
            el.innerText = count;
        }
    });

    // 旧全选 Banner 兼容
    const banner = document.getElementById(`${tableId}-selection-banner`);
    if (banner) {
        banner.style.display = (count > 0 || isAllMode) ? 'flex' : 'none';
        if (isAllMode) {
            banner.classList.add('all-filtered-active');
        } else {
            banner.classList.remove('all-filtered-active');
        }
    }

    // pan-relay 风格底部悬浮胶囊工具栏控制
    const floatingToolbar = document.getElementById(`${tableId}-floating-toolbar`);
    if (floatingToolbar) {
        if (count > 0 || isAllMode) {
            floatingToolbar.classList.add('show');
        } else {
            floatingToolbar.classList.remove('show');
        }
    }
}


/**
 * 清空指定表格的选择状态
 */
function clearTableSelection(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;

    table.removeAttribute('data-select-mode');
    table.removeAttribute('data-total-count');

    const selectAllCheckbox = document.querySelector(`.table-select-all[data-table="${tableId}"]`);
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = false;
        selectAllCheckbox.indeterminate = false;
    }

    table.querySelectorAll('.row-checkbox').forEach(cb => {
        cb.checked = false;
    });

    updateSelectionState(tableId);
}

/**
 * 跨页选择模式指示
 */
function setSelectAllFilteredMode(tableId, totalCount) {
    const banner = document.getElementById(`${tableId}-selection-banner`);
    const countText = document.getElementById(`${tableId}-selected-count`);
    const modeInput = document.getElementById(`${tableId}-select-mode`);

    if (modeInput) modeInput.value = 'all';
    if (countText) countText.innerText = `全部 ${totalCount}`;
    if (banner) {
        banner.classList.add('all-filtered-active');
    }
}

/**
 * 核心批量操作提交接口
 */
async function executeBatchAction(tableId, targetUrl, action, extraPayload = {}, confirmPrompt = '', confirmTitle = '操作确认', confirmType = 'danger') {
    const table = document.getElementById(tableId);
    if (!table) return;

    const isAllMode = table.getAttribute('data-select-mode') === 'all';
    const checkedBoxes = table.querySelectorAll('.row-checkbox:checked');
    const values = Array.from(checkedBoxes).map(cb => cb.value);

    if (!isAllMode && values.length === 0) {
        if (window.showToast) {
            window.showToast('请先勾选需要批量操作的行！', 'warning');
        }
        return;
    }

    if (confirmPrompt) {
        if (window.confirmModal) {
            const ok = await window.confirmModal({
                title: confirmTitle,
                message: confirmPrompt,
                confirmText: '确定',
                type: confirmType
            });
            if (!ok) return;
        } else if (typeof confirm === 'function' && !confirm(confirmPrompt)) {
            return;
        }
    }

    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content ||
                      document.querySelector('input[name="csrf_token"]')?.value || '';

    const form = document.createElement('form');
    form.method = 'POST';
    form.action = targetUrl;

    const fields = {
        csrf_token: csrfToken,
        action: action,
        select_mode: isAllMode ? 'all' : 'page',
        [tableId.startsWith('platforms') ? 'names' : 'ids']: values.join(','),
        ...extraPayload
    };

    for (const [key, val] of Object.entries(fields)) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = key;
        input.value = val;
        form.appendChild(input);
    }

    document.body.appendChild(form);
    form.submit();
}

/**
 * 随机强密码生成器
 */
function generateRandomPassword(length = 12) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
    let res = '';
    for (let i = 0; i < length; i++) {
        res += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return res;
}

/**
 * 导出运行日志
 */
function triggerLogExport(exportType = 'auto') {
    const urlParams = new URLSearchParams(window.location.search);
    const logsTable = document.getElementById('logs-table');
    const isAllMode = logsTable && logsTable.getAttribute('data-select-mode') === 'all';
    const checkedBoxes = document.querySelectorAll('#logs-table .row-checkbox:checked');
    const ids = Array.from(checkedBoxes).map(cb => cb.value);

    if (exportType === 'auto') {
        if (isAllMode) {
            exportType = 'all';
        } else {
            exportType = ids.length > 0 ? 'selected' : 'all';
        }
    } else if (exportType === 'selected' && isAllMode) {
        exportType = 'all';
    }

    urlParams.set('export_type', exportType);

    if (exportType === 'selected') {
        if (ids.length === 0) {
            if (window.showToast) {
                window.showToast('请先勾选需要导出的日志条目！', 'warning');
            }
            return;
        }
        urlParams.set('ids', ids.join(','));
    } else {
        urlParams.delete('ids');
    }

    const exportBase = window.location.pathname.startsWith('/console') ? '/console/logs/export.csv' : '/admin/logs/export.csv';
    window.location.href = `${exportBase}?${urlParams.toString()}`;
}


/**
 * 打开 / 关闭 批量操作 Modal
 */
function openBatchModal(modalId, tableId) {
    const m = document.getElementById(modalId);
    if (!m) return;
    const checked = document.querySelectorAll(`#${tableId} .row-checkbox:checked`);
    if (checked.length === 0) {
        if (window.showToast) {
            window.showToast('请先勾选需要批量操作的项！', 'warning');
        }
        return;
    }
    m.style.display = 'flex';
    void m.offsetHeight;
    m.classList.add('modal-open');
}

function closeBatchModal(modalId) {
    const m = document.getElementById(modalId);
    if (!m) return;
    m.classList.remove('modal-open');
    setTimeout(() => { m.style.display = 'none'; }, 180);
}

function submitBatchUserCredits() {
    let mode = document.getElementById('batch-credits-mode')?.value || 'add';
    let amount = document.getElementById('batch-credits-amount')?.value || '0';
    if (mode === 'unlimited') {
        mode = 'set';
        amount = '-1';
    }
    executeBatchAction('users-table', '/admin/users/batch', 'adjust_credits', { credits_mode: mode, credits_amount: amount });
}

function submitBatchUserExpires() {
    const expires = document.getElementById('batch-expires-date')?.value || '';
    if (!expires) {
        if (window.showToast) {
            window.showToast('请选择到期日期！', 'warning');
        }
        return;
    }
    executeBatchAction('users-table', '/admin/users/batch', 'set_expires', { expires_at: expires });
}

function submitBatchUserQps() {
    const qps = document.getElementById('batch-user-qps-val')?.value || '2';
    executeBatchAction('users-table', '/admin/users/batch', 'set_qps', { qps_limit: qps });
}

function submitBatchKeyQps() {
    const qps = document.getElementById('batch-key-qps-val')?.value || '';
    executeBatchAction('keys-table', '/admin/keys/batch', 'set_qps', { qps_limit: qps });
}

function submitBatchPlatformQps() {
    const qps = document.getElementById('batch-platform-qps-val')?.value || '';
    executeBatchAction('platforms-table', '/admin/platforms/batch', 'set_qps', { qps_limit: qps });
}

/**
 * ==========================================================================
 * 轻量级网页自定义下拉菜单组件 (替代系统原生 <select> 灰色弹窗)
 * ==========================================================================
 */
function initCustomSelects() {
    document.querySelectorAll('select:not(.native-select)').forEach(sel => {
        if (sel.dataset.customSelectInit === 'true') return;
        sel.dataset.customSelectInit = 'true';
        sel.style.display = 'none';

        const wrap = document.createElement('div');
        wrap.className = 'custom-select-wrap';
        if (sel.className) {
            sel.className.split(/\s+/).forEach(c => {
                if (c) wrap.classList.add(c + '-wrap');
            });
            if (sel.classList.contains('w-full')) {
                wrap.classList.add('w-full');
            }
        }
        if (sel.id) wrap.id = sel.id + '-custom-wrap';

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'custom-select-btn';

        const btnText = document.createElement('span');
        btnText.className = 'custom-select-btn-text';

        const chevron = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        chevron.setAttribute('class', 'custom-select-chevron');
        chevron.setAttribute('width', '11');
        chevron.setAttribute('height', '11');
        chevron.setAttribute('viewBox', '0 0 24 24');
        chevron.setAttribute('fill', 'none');
        chevron.setAttribute('stroke', 'currentColor');
        chevron.setAttribute('stroke-width', '2.5');
        chevron.setAttribute('stroke-linecap', 'round');
        chevron.setAttribute('stroke-linejoin', 'round');
        chevron.innerHTML = '<polyline points="6 9 12 15 18 9"></polyline>';

        btn.appendChild(btnText);
        btn.appendChild(chevron);
        wrap.appendChild(btn);

        // Measure widest option to lock button width and avoid width shifts upon selection
        let maxOptionWidth = 0;
        try {
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            if (context) {
                context.font = '500 12px system-ui, -apple-system, sans-serif';
                Array.from(sel.options).forEach(opt => {
                    const textWidth = context.measureText(opt.text || '').width;
                    if (textWidth > maxOptionWidth) maxOptionWidth = textWidth;
                });
            }
        } catch (e) {}

        if (maxOptionWidth > 0) {
            const calcMinWidth = Math.ceil(maxOptionWidth + 49);
            btn.style.minWidth = `${calcMinWidth}px`;
        }

        const popover = document.createElement('div');
        popover.className = 'custom-select-popover';

        function updateOptions() {
            popover.innerHTML = '';
            const currVal = sel.value;
            let foundText = '';

            Array.from(sel.children).forEach(child => {
                if (child.tagName === 'OPTGROUP') {
                    const header = document.createElement('div');
                    header.className = 'custom-select-group-header';
                    header.textContent = child.label || '';
                    popover.appendChild(header);

                    Array.from(child.children).forEach(opt => {
                        const item = renderItem(opt, currVal);
                        if (opt.value === currVal || opt.selected) foundText = opt.text;
                        popover.appendChild(item);
                    });
                } else if (child.tagName === 'OPTION') {
                    const item = renderItem(child, currVal);
                    if (child.value === currVal || child.selected) foundText = child.text;
                    popover.appendChild(item);
                }
            });

            const activeOpt = sel.options[sel.selectedIndex];
            btnText.textContent = foundText || (activeOpt ? activeOpt.text : '') || '请选择';
        }

        function renderItem(opt, currVal) {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'custom-select-item' + (opt.value === currVal ? ' active' : '');
            item.dataset.value = opt.value;

            const t = document.createElement('span');
            t.className = 'custom-select-item-text';
            t.textContent = opt.text;

            const chk = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            chk.setAttribute('class', 'custom-select-item-check');
            chk.setAttribute('width', '13');
            chk.setAttribute('height', '13');
            chk.setAttribute('viewBox', '0 0 24 24');
            chk.setAttribute('fill', 'none');
            chk.setAttribute('stroke', 'currentColor');
            chk.setAttribute('stroke-width', '2.5');
            chk.setAttribute('stroke-linecap', 'round');
            chk.setAttribute('stroke-linejoin', 'round');
            chk.innerHTML = '<polyline points="20 6 9 17 4 12"></polyline>';

            item.appendChild(t);
            item.appendChild(chk);

            item.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                sel.value = opt.value;
                btnText.textContent = opt.text;
                wrap.classList.remove('open');

                popover.querySelectorAll('.custom-select-item').forEach(el => {
                    if (el.dataset.value === opt.value) el.classList.add('active');
                    else el.classList.remove('active');
                });

                sel.dispatchEvent(new Event('change', { bubbles: true }));
                if (typeof sel.onchange === 'function') {
                    sel.onchange.call(sel, new Event('change'));
                }
            };
            return item;
        }

        updateOptions();

        btn.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            const isOpen = wrap.classList.contains('open');

            document.querySelectorAll('.custom-select-wrap.open').forEach(w => {
                if (w !== wrap) w.classList.remove('open');
            });

            if (!isOpen) {
                const rect = btn.getBoundingClientRect();
                const spaceBelow = window.innerHeight - rect.bottom;
                const spaceAbove = rect.top;
                if (spaceBelow < 200 && spaceAbove > spaceBelow) {
                    wrap.classList.add('drop-up');
                } else {
                    wrap.classList.remove('drop-up');
                }
                wrap.classList.add('open');
            } else {
                wrap.classList.remove('open');
            }
        };

        sel.addEventListener('change', () => {
            const activeOpt = sel.options[sel.selectedIndex];
            if (activeOpt) {
                btnText.textContent = activeOpt.text;
                popover.querySelectorAll('.custom-select-item').forEach(el => {
                    if (el.dataset.value === sel.value) el.classList.add('active');
                    else el.classList.remove('active');
                });
            }
        });

        wrap.appendChild(popover);
        sel.parentNode.insertBefore(wrap, sel.nextSibling);
    });
}

document.addEventListener('click', (e) => {
    if (!e.target.closest('.custom-select-wrap')) {
        document.querySelectorAll('.custom-select-wrap.open').forEach(w => {
            w.classList.remove('open');
        });
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.custom-select-wrap.open').forEach(w => {
            w.classList.remove('open');
        });
    }
});

window.initCustomSelects = initCustomSelects;

