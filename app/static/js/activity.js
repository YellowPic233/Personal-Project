import { api } from './api.js';
import { $, categoryTag, clearFormError, formatDate, formatRange, initIcons, renderState, setButtonBusy, showFormError, statusTag } from './ui.js?v=20261027';

initIcons();
const activityId = location.pathname.split('/').filter(Boolean).at(-1);
const form = $('#registration-form');
let activity;
let submitting = false;
let registered = false;
let activityMissing = false;

function updateAvailability() {
  $('#remaining-count').innerHTML = `还剩 <strong>${activity.remaining_capacity}</strong> 个名额`;
  $('#detail-status').innerHTML = statusTag(activity.registration_status);
  const unavailable = activity.registration_status !== 'open';
  $('#registration-fields').disabled = unavailable || submitting || activityMissing;
  const notice = $('#registration-notice');
  notice.replaceChildren(); notice.hidden = !unavailable || registered;
  if (unavailable && !registered) {
    notice.append(document.createTextNode(activity.registration_status === 'full' ? '这场活动名额已满，暂时无法报名。' : '报名已截止或活动已开始，暂时无法报名。'));
    const retry = document.createElement('button'); retry.className = 'button secondary small'; retry.type = 'button'; retry.textContent = '刷新活动状态';
    retry.addEventListener('click', refreshAvailability); notice.append(document.createElement('br'), retry);
  }
}

function renderActivity() {
  document.title = `${activity.title} · 校园有约`;
  $('#detail-title').textContent = activity.title;
  $('#detail-category').outerHTML = categoryTag(activity.category).replace('class="category-tag"', 'id="detail-category" class="category-tag"');
  $('#detail-club').textContent = activity.club_name;
  $('#detail-time').textContent = formatRange(activity.starts_at, activity.ends_at);
  $('#detail-location').textContent = activity.location;
  $('#detail-deadline').textContent = formatDate(activity.registration_deadline);
  $('#detail-capacity').textContent = `${activity.capacity} 人 · 已报名 ${activity.registration_count} 人`;
  $('#detail-description').textContent = activity.description;
  updateAvailability();
}

async function loadActivity() {
  $('#detail-layout').hidden = true; $('#detail-state').hidden = false;
  renderState($('#detail-state'), { kind: 'loading', title: '正在加载活动详情' });
  try {
    activity = await api(`/activities/${encodeURIComponent(activityId)}`);
    renderActivity(); $('#detail-state').hidden = true; $('#detail-layout').hidden = false;
  } catch (error) {
    renderState($('#detail-state'), { kind: 'error', title: error.status === 404 ? '这场活动暂时找不到了' : '活动详情加载失败',
      message: error.status === 404 ? '活动可能已被删除，回到广场看看其他活动吧。' : error.message,
      action: error.status === 404 ? '返回活动广场' : '重新加载',
      onAction: error.status === 404 ? () => { location.href = '/'; } : loadActivity });
  }
}

async function refreshAvailability() {
  try {
    activity = await api(`/activities/${encodeURIComponent(activityId)}`); renderActivity();
  } catch (error) {
    if (registered) {
      $('#success-message').textContent += ' 报名已保存，活动最新名额暂未刷新。';
    } else {
      showFormError(form, $('#registration-error'), error);
      if (error.status === 404) { activityMissing = true; $('#registration-fields').disabled = true; }
    }
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault(); if (submitting || registered || activity?.registration_status !== 'open') return;
  clearFormError(form, $('#registration-error'));
  if (!form.reportValidity()) return;
  const data = Object.fromEntries(new FormData(form));
  for (const key of Object.keys(data)) data[key] = data[key].trim();
  submitting = true; setButtonBusy($('#registration-submit'), true, '正在报名…');
  $('#registration-fields').disabled = true;
  try {
    const result = await api(`/activities/${activity.id}/registrations`, { method: 'POST', body: data });
    registered = true;
    $('#success-message').textContent = `${result.name}，你已成功报名「${activity.title}」。报名编号：${result.id}。`;
    form.hidden = true; $('#registration-notice').hidden = true; $('#registration-success').hidden = false;
    $('#registration-success').focus();
    await refreshAvailability();
  } catch (error) {
    showFormError(form, $('#registration-error'), error);
    if (['ACTIVITY_FULL', 'REGISTRATION_CLOSED', 'ACTIVITY_NOT_FOUND'].includes(error.code)) await refreshAvailability();
  } finally {
    submitting = false; setButtonBusy($('#registration-submit'), false);
    if (!registered) $('#registration-fields').disabled = activityMissing || activity?.registration_status !== 'open';
  }
});

loadActivity();
