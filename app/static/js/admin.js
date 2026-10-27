import { api, queryString } from './api.js';
import { $, categoryTag, clearFormError, escapeHTML, formatDate, fromChinaInput, initIcons, inlineError,
  renderPagination, renderState, setButtonBusy, setDialogBusy, showFormError, statusTag, toast, toChinaInput, bindDialog } from './ui.js?v=20261027';

initIcons();
const state = { q: '', category: '', page: 1, page_size: 10 };
const editor = $('#editor-dialog');
const editorForm = $('#editor-form');
const roster = $('#roster-dialog');
const deleteDialog = $('#delete-dialog');
for (const dialog of [editor, roster, deleteDialog]) bindDialog(dialog);
let listController;
let editorController;
let rosterController;
let deleteController;
let editingId = null;
let deleteTarget = null;
let rosterId = null;
let rosterPage = 1;
let statsVersion = 0;

async function loadCategories() {
  $('#category-error').hidden = true; $('#create-activity').disabled = true; $('#admin-category').disabled = true;
  try {
    const categories = await api('/categories');
    const filter = $('#admin-category'); const selected = state.category;
    filter.replaceChildren(new Option('全部分类', ''));
    $('#edit-category').replaceChildren(new Option('请选择分类', ''));
    for (const category of categories) {
      filter.add(new Option(category, category)); $('#edit-category').add(new Option(category, category));
    }
    filter.value = selected; filter.disabled = false; $('#create-activity').disabled = false;
  } catch (error) { inlineError($('#category-error'), error, loadCategories); }
}

async function loadStats() {
  const version = ++statsVersion;
  $('#stats').setAttribute('aria-busy', 'true'); $('#stats-error').hidden = true;
  try {
    const data = await api('/admin/stats'); if (version !== statsVersion) return;
    $('#stat-activities').textContent = data.activity_count;
    $('#stat-registrations').textContent = data.registration_count;
    $('#stat-students').textContent = data.unique_student_count;
  } catch (error) {
    if (version !== statsVersion) return;
    for (const selector of ['#stat-activities', '#stat-registrations', '#stat-students']) $(selector).textContent = '—';
    inlineError($('#stats-error'), error, loadStats);
  } finally { if (version === statsVersion) $('#stats').setAttribute('aria-busy', 'false'); }
}

async function loadActivities() {
  listController?.abort(); listController = new AbortController(); const current = listController;
  $('#admin-pagination').replaceChildren(); $('#admin-total').textContent = '正在加载…';
  renderState($('#admin-list'), { kind: 'loading', title: '正在加载活动列表' });
  try {
    const data = await api(`/admin/activities?${queryString(state)}`, { signal: current.signal });
    if (current !== listController) return;
    if (data.total && !data.items.length && state.page > 1) {
      state.page = Math.ceil(data.total / state.page_size); return loadActivities();
    }
    $('#admin-total').textContent = `共 ${data.total} 场活动`;
    if (!data.items.length) {
      renderState($('#admin-list'), { title: state.q || state.category ? '没有找到匹配的活动' : '还没有发布活动',
        message: state.q || state.category ? '试试其他关键词或分类。' : '点击「创建活动」，发布社团的第一场精彩活动。',
        action: state.q || state.category ? '清除筛选' : undefined,
        onAction: () => { resetFilters(); loadActivities(); } });
      return;
    }
    $('#admin-list').setAttribute('aria-busy', 'false');
    $('#admin-list').innerHTML = `<div class="table-wrap"><table class="mobile-stack"><caption class="sr-only">活动管理列表</caption>
      <thead><tr><th scope="col">活动</th><th scope="col">分类</th><th scope="col">开始时间</th><th scope="col">报名人数</th><th scope="col">状态</th><th scope="col">操作</th></tr></thead>
      <tbody>${data.items.map((activity) => `<tr>
        <td class="activity-cell"><a href="/activities/${activity.id}">${escapeHTML(activity.title)}</a><p>${escapeHTML(activity.club_name)}</p></td>
        <td data-label="分类">${categoryTag(activity.category)}</td><td class="time-cell" data-label="开始时间">${escapeHTML(formatDate(activity.starts_at))}</td>
        <td class="number-cell" data-label="报名人数">${activity.registration_count} / ${activity.capacity}</td><td data-label="状态">${statusTag(activity.registration_status)}</td>
        <td class="action-cell"><div class="row-actions"><button class="text-button" type="button" data-action="roster" data-id="${activity.id}">报名名单</button>
        <button class="text-button" type="button" data-action="edit" data-id="${activity.id}">编辑</button><button class="text-button danger-text" type="button" data-action="delete" data-id="${activity.id}">删除</button></div></td>
      </tr>`).join('')}</tbody></table></div>`;
    renderPagination($('#admin-pagination'), data, (page) => { state.page = page; loadActivities(); });
  } catch (error) {
    if (error.name === 'AbortError' || current !== listController) return;
    $('#admin-total').textContent = '加载失败';
    renderState($('#admin-list'), { kind: 'error', title: '活动列表加载失败', message: error.message, action: '重新加载', onAction: loadActivities });
  }
}

function resetFilters() {
  Object.assign(state, { q: '', category: '', page: 1 }); $('#admin-q').value = ''; $('#admin-category').value = '';
}
function refreshDashboard() { return Promise.all([loadStats(), loadActivities()]); }

async function openEditor(id = null) {
  if (editor.open) return;
  editingId = id; editorForm.reset(); clearFormError(editorForm, $('#editor-error'));
  $('#editor-title').textContent = id ? '编辑活动' : '创建活动';
  $('#editor-submit').textContent = id ? '保存修改' : '创建活动';
  $('#editor-submit').disabled = false; $('#editor-fields').disabled = false;
  $('#editor-loading').hidden = !id; editorForm.hidden = Boolean(id); editor.showModal();
  if (!id) { $('#edit-title').focus(); return; }
  await loadEditorData(id);
}

async function loadEditorData(id) {
  editorController?.abort(); editorController = new AbortController(); const current = editorController;
  $('#editor-loading').hidden = false; editorForm.hidden = true;
  renderState($('#editor-loading'), { kind: 'loading', title: '正在获取最新活动信息' });
  try {
    const activity = await api(`/activities/${id}`, { signal: current.signal });
    if (current !== editorController || !editor.open) return;
    for (const field of ['title', 'club_name', 'category', 'location', 'description', 'capacity']) editorForm.elements.namedItem(field).value = activity[field];
    for (const field of ['starts_at', 'ends_at', 'registration_deadline']) editorForm.elements.namedItem(field).value = toChinaInput(activity[field]);
    $('#editor-loading').hidden = true; editorForm.hidden = false; $('#edit-title').focus();
  } catch (error) {
    if (error.name === 'AbortError') return;
    renderState($('#editor-loading'), { kind: 'error', title: '无法加载编辑信息', message: error.message, action: '重新加载',
      onAction: () => loadEditorData(id) });
  }
}
editor.addEventListener('close', () => { editorController?.abort(); });

editorForm.addEventListener('submit', async (event) => {
  event.preventDefault(); if (editor.dataset.busy === 'true') return;
  clearFormError(editorForm, $('#editor-error')); if (!editorForm.reportValidity()) return;
  const data = Object.fromEntries(new FormData(editorForm));
  for (const key of Object.keys(data)) data[key] = data[key].trim();
  data.capacity = Number(data.capacity);
  try {
    for (const field of ['starts_at', 'ends_at', 'registration_deadline']) data[field] = fromChinaInput(data[field]);
  } catch {
    showFormError(editorForm, $('#editor-error'), { message: '请填写有效的开始、结束及报名截止时间。' }); return;
  }
  setDialogBusy(editor, true); setButtonBusy($('#editor-submit'), true, editingId ? '正在保存…' : '正在创建…'); $('#editor-fields').disabled = true;
  try {
    await api(editingId ? `/admin/activities/${editingId}` : '/admin/activities', { method: editingId ? 'PUT' : 'POST', body: data });
    toast(editingId ? '活动修改已保存。' : '活动创建成功，现在可以在活动广场查看。');
    if (!editingId) resetFilters();
    editor.close(); refreshDashboard();
  } catch (error) { showFormError(editorForm, $('#editor-error'), error); }
  finally { setDialogBusy(editor, false); setButtonBusy($('#editor-submit'), false); $('#editor-fields').disabled = false; }
});

async function openRoster(id) {
  rosterId = id; rosterPage = 1;
  $('#roster-title').textContent = '报名名单'; $('#roster-subtitle').textContent = '';
  roster.showModal(); await loadRoster();
}
async function loadRoster() {
  rosterController?.abort(); rosterController = new AbortController(); const current = rosterController;
  const id = rosterId; const page = rosterPage;
  $('#roster-pagination').replaceChildren();
  renderState($('#roster-content'), { kind: 'loading', title: '正在加载报名名单' });
  try {
    const [activity, data] = await Promise.all([
      api(`/activities/${id}`, { signal: current.signal }),
      api(`/admin/activities/${id}/registrations?${queryString({ page, page_size: 10 })}`, { signal: current.signal }),
    ]);
    if (current !== rosterController || !roster.open) return;
    $('#roster-subtitle').textContent = `${activity.title} · 共 ${data.total} 人报名`;
    if (!data.items.length) {
      renderState($('#roster-content'), { title: '暂时还没有人报名', message: '同学们提交报名后，名单会显示在这里。' }); return;
    }
    $('#roster-content').setAttribute('aria-busy', 'false');
    $('#roster-content').innerHTML = `<div class="table-wrap" tabindex="0" role="region" aria-label="报名名单，可横向滚动"><table class="roster-table"><caption class="sr-only">${escapeHTML(activity.title)}报名名单</caption>
      <thead><tr><th scope="col">姓名</th><th scope="col">学号</th><th scope="col">联系方式</th><th scope="col">报名时间</th></tr></thead>
      <tbody>${data.items.map((item) => `<tr><td>${escapeHTML(item.name)}</td><td>${escapeHTML(item.student_id)}</td><td>${escapeHTML(item.contact)}</td><td class="time-cell">${escapeHTML(formatDate(item.created_at))}</td></tr>`).join('')}</tbody></table></div>`;
    renderPagination($('#roster-pagination'), data, (newPage) => { rosterPage = newPage; loadRoster(); });
  } catch (error) {
    if (error.name === 'AbortError' || current !== rosterController) return;
    renderState($('#roster-content'), { kind: 'error', title: '报名名单加载失败', message: error.message, action: '重新加载', onAction: loadRoster });
  }
}
roster.addEventListener('close', () => {
  rosterController?.abort(); $('#roster-content').replaceChildren(); $('#roster-subtitle').textContent = '';
});

async function openDelete(id) {
  deleteTarget = null; deleteController?.abort(); deleteController = new AbortController(); const current = deleteController;
  $('#delete-error').hidden = true; $('#delete-message').textContent = '正在确认活动和报名人数…';
  $('#confirm-delete').disabled = true; deleteDialog.showModal();
  try {
    const activity = await api(`/activities/${id}`, { signal: current.signal });
    if (!deleteDialog.open || current !== deleteController) return;
    deleteTarget = activity;
    $('#delete-message').textContent = `确定删除「${activity.title}」吗？当前有 ${activity.registration_count} 条关联报名记录。`;
    $('#confirm-delete').disabled = false;
  } catch (error) {
    if (error.name === 'AbortError') return;
    $('#delete-message').textContent = error.message;
  }
}
deleteDialog.addEventListener('close', () => { deleteController?.abort(); deleteTarget = null; });
$('#confirm-delete').addEventListener('click', async () => {
  if (!deleteTarget || deleteDialog.dataset.busy === 'true') return;
  setDialogBusy(deleteDialog, true); setButtonBusy($('#confirm-delete'), true, '正在删除…');
  $('#delete-error').hidden = true;
  try {
    await api(`/admin/activities/${deleteTarget.id}`, { method: 'DELETE' });
    deleteDialog.close(); toast('活动及关联报名已删除。'); refreshDashboard();
  } catch (error) {
    $('#delete-error').textContent = error.message; $('#delete-error').hidden = false; $('#delete-error').focus();
  } finally { setDialogBusy(deleteDialog, false); setButtonBusy($('#confirm-delete'), false); }
});

$('#create-activity').addEventListener('click', () => openEditor());
$('#admin-search').addEventListener('submit', (event) => {
  event.preventDefault(); state.q = $('#admin-q').value.trim(); state.category = $('#admin-category').value; state.page = 1; loadActivities();
});
$('#admin-category').addEventListener('change', () => {
  state.q = $('#admin-q').value.trim(); state.category = $('#admin-category').value; state.page = 1; loadActivities();
});
$('#refresh-dashboard').addEventListener('click', () => { loadCategories(); refreshDashboard(); });
$('#admin-list').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-action]'); if (!button) return;
  const id = Number(button.dataset.id);
  if (button.dataset.action === 'edit') openEditor(id);
  if (button.dataset.action === 'roster') openRoster(id);
  if (button.dataset.action === 'delete') openDelete(id);
});
loadCategories(); refreshDashboard();
