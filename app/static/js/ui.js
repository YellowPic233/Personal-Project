// 可复用 UI 与安全的文本输出。所有 API 返回的文本在插入 HTML 前必须转义。
export const $ = (selector, parent = document) => parent.querySelector(selector);
export const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[character]);

const paths = {
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18"/>',
  pin: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
  users: '<circle cx="9" cy="7" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 5v2"/>',
  user: '<circle cx="12" cy="7" r="3.5"/><path d="M5 21v-2a7 7 0 0 1 14 0v2"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  left: '<path d="m14 5-7 7 7 7"/>',
  plus: '<path d="M12 4v16M4 12h16"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>',
  empty: '<path d="M4 5h16v16H4zM8 2v6m8-6v6M4 11h16m-12 5h8"/>',
  refresh: '<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',
};
export const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.info}</svg>`;
export function initIcons(root = document) {
  root.querySelectorAll('[data-icon]').forEach((element) => { element.innerHTML = icon(element.dataset.icon); });
}

const dateFormat = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});
export const formatDate = (value) => dateFormat.format(new Date(value));
const dayFormat = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' });
const timeFormat = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
export const formatRange = (start, end) => {
  const sameDay = dayFormat.format(new Date(start)) === dayFormat.format(new Date(end));
  return `${formatDate(start)} — ${sameDay ? timeFormat.format(new Date(end)) : formatDate(end)}`;
};
// datetime-local 中显示中国时间，不受操作系统时区影响。
export const toChinaInput = (value) => new Date(new Date(value).getTime() + 8 * 3600000).toISOString().slice(0, 23);
export const fromChinaInput = (value) => new Date(`${value}+08:00`).toISOString();

const statusLabels = { open: '报名中', full: '名额已满', closed: '报名已截止' };
export const statusTag = (status) => `<span class="status-tag" data-status="${escapeHTML(status)}">${statusLabels[status] || '状态未知'}</span>`;
export const categoryTag = (category) => `<span class="category-tag" data-category="${escapeHTML(category)}">${escapeHTML(category)}</span>`;

export function renderState(container, { kind = 'empty', title, message = '', action, onAction }) {
  container.setAttribute('aria-busy', kind === 'loading' ? 'true' : 'false');
  container.innerHTML = `<div class="state-panel" role="${kind === 'error' ? 'alert' : 'status'}">
    ${kind === 'loading' ? '<span class="spinner" aria-hidden="true"></span>' : icon(kind === 'error' ? 'info' : 'empty')}
    <h3>${escapeHTML(title)}</h3><p>${escapeHTML(message)}</p>
    ${action ? `<button class="button secondary" type="button">${escapeHTML(action)}</button>` : ''}</div>`;
  if (action) $('button', container).addEventListener('click', onAction);
}

export function renderPagination(container, data, onPage) {
  container.replaceChildren();
  if (!data.total) return;
  const pages = Math.ceil(data.total / data.page_size);
  const previous = document.createElement('button');
  previous.type = 'button'; previous.className = 'button secondary small'; previous.textContent = '上一页';
  previous.disabled = data.page <= 1; previous.addEventListener('click', () => onPage(data.page - 1));
  const next = document.createElement('button');
  next.type = 'button'; next.className = 'button secondary small'; next.textContent = '下一页';
  next.disabled = data.page >= pages; next.addEventListener('click', () => onPage(data.page + 1));
  const label = document.createElement('span'); label.className = 'page-label';
  label.textContent = `第 ${data.page} / ${pages} 页 · 共 ${data.total} 项`;
  container.append(previous, label, next);
}

export function inlineError(container, error, retry) {
  container.replaceChildren(document.createTextNode(error.message));
  container.hidden = false;
  if (retry) {
    const button = document.createElement('button'); button.type = 'button';
    button.className = 'button secondary small'; button.textContent = '重试';
    button.addEventListener('click', retry); container.append(button);
  }
}

export function toast(message) {
  const region = $('#toasts'); if (!region) return;
  const element = document.createElement('div'); element.className = 'toast'; element.setAttribute('role', 'status');
  const text = document.createElement('p'); text.textContent = message;
  const close = document.createElement('button'); close.type = 'button'; close.className = 'icon-button';
  close.setAttribute('aria-label', '关闭通知'); close.innerHTML = icon('close');
  close.addEventListener('click', () => element.remove()); element.append(text, close); region.append(element);
  setTimeout(() => element.remove(), 7000);
}

const labels = {
  title: '活动名称', club_name: '主办社团', category: '活动分类', location: '活动地点', description: '活动介绍',
  capacity: '活动名额', starts_at: '开始时间', ends_at: '结束时间', registration_deadline: '报名截止',
  name: '姓名', student_id: '学号', contact: '联系方式',
};
function validationMessage(detail) {
  const messages = {
    missing: '请填写此项。', string_too_short: '内容不能为空。', string_too_long: '内容超过允许长度。',
    string_pattern_mismatch: '请仅使用字母、数字、下划线和连字符。', int_type: '请输入整数。',
    greater_than_equal: '数值小于允许的最小值。', less_than_equal: '数值超过允许的最大值。',
    timezone_aware: '时间必须包含时区。', enum: '请选择有效的活动分类。',
  };
  return messages[detail.type] || (detail.message || '输入不合法。').replace(/^Value error, /, '');
}

export function clearFormError(form, summary) {
  summary.hidden = true; summary.replaceChildren();
  form.querySelectorAll('[aria-invalid]').forEach((input) => input.removeAttribute('aria-invalid'));
  form.querySelectorAll('[data-error-field]').forEach((element) => { element.hidden = true; element.textContent = ''; });
}

export function showFormError(form, summary, error) {
  clearFormError(form, summary);
  const heading = document.createElement('p'); heading.textContent = error.message; summary.append(heading);
  if (error.details?.length) {
    const list = document.createElement('ul');
    for (const detail of error.details) {
      const field = detail.field?.split('.').at(-1);
      const message = validationMessage(detail);
      const item = document.createElement('li'); item.textContent = `${labels[field] ? `${labels[field]}：` : ''}${message}`;
      list.append(item);
      // 不把服务器返回的字段名拼接到选择器中。
      const input = form.elements.namedItem(field);
      if (input?.setAttribute) input.setAttribute('aria-invalid', 'true');
      const target = [...form.querySelectorAll('[data-error-field]')].find((element) => element.dataset.errorField === field);
      if (target) { target.textContent = message; target.hidden = false; }
    }
    summary.append(list);
  }
  summary.hidden = false; summary.focus();
}

export function setButtonBusy(button, busy, label) {
  if (busy) {
    button.dataset.idleLabel = button.textContent; button.textContent = label || '正在提交…';
    button.disabled = true; button.setAttribute('aria-busy', 'true');
  } else {
    button.textContent = button.dataset.idleLabel || label || button.textContent;
    button.disabled = false; button.removeAttribute('aria-busy');
  }
}

export function bindDialog(dialog) {
  dialog.querySelectorAll('[data-close]').forEach((button) => button.addEventListener('click', () => {
    if (dialog.dataset.busy !== 'true') dialog.close();
  }));
  dialog.addEventListener('cancel', (event) => { if (dialog.dataset.busy === 'true') event.preventDefault(); });
}
export function setDialogBusy(dialog, busy) {
  dialog.dataset.busy = String(busy);
  dialog.querySelectorAll('[data-close]').forEach((button) => { button.disabled = busy; });
}
