import { api, queryString } from './api.js';
import { $, categoryTag, escapeHTML, formatRange, icon, initIcons, inlineError, renderPagination, renderState, statusTag } from './ui.js?v=20261027';

initIcons();
const params = new URLSearchParams(location.search);
const state = { q: (params.get('q') || '').slice(0, 100), category: params.get('category') || '',
  page: Math.max(1, Math.min(1000000, Number.parseInt(params.get('page'), 10) || 1)), page_size: 9 };
$('#search').value = state.q;
let requestController;

function updateURL() {
  const query = queryString({ q: state.q, category: state.category, page: state.page > 1 ? state.page : '' });
  history.replaceState(null, '', `${location.pathname}${query ? `?${query}` : ''}`);
}

async function loadCategories() {
  $('#category-error').hidden = true;
  try {
    const categories = await api('/categories');
    const holder = $('#category-filters'); holder.replaceChildren();
    for (const category of ['', ...categories]) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'filter-button';
      button.textContent = category || '全部活动'; button.dataset.category = category;
      button.setAttribute('aria-pressed', String(state.category === category));
      button.addEventListener('click', () => {
        state.category = category; state.page = 1;
        holder.querySelectorAll('button').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
        loadActivities();
      });
      holder.append(button);
    }
  } catch (error) {
    $('#category-filters').replaceChildren();
    inlineError($('#category-error'), error, loadCategories);
  }
}

async function loadActivities() {
  requestController?.abort(); requestController = new AbortController();
  const current = requestController;
  updateURL(); $('#pagination').replaceChildren(); $('#results-count').textContent = '正在获取活动…';
  renderState($('#activity-list'), { kind: 'loading', title: '正在加载活动', message: '精彩的校园生活，马上呈现。' });
  try {
    const data = await api(`/activities?${queryString(state)}`, { signal: current.signal });
    if (current !== requestController) return;
    if (data.total && !data.items.length && state.page > 1) {
      state.page = Math.ceil(data.total / state.page_size); return loadActivities();
    }
    $('#results-count').textContent = `共 ${data.total} 场活动`;
    $('#activity-list').setAttribute('aria-busy', 'false');
    if (!data.items.length) {
      renderState($('#activity-list'), { title: state.q || state.category ? '没有找到匹配的活动' : '新的校园故事，等你开启',
        message: state.q || state.category ? '换个关键词或分类，再探索一下吧。' : '暂时还没有活动，社团发布后会出现在这里。',
        action: state.q || state.category ? '清除筛选' : '前往管理后台',
        onAction: () => {
          if (!state.q && !state.category) { location.href = '/admin'; return; }
          state.q = ''; state.category = ''; state.page = 1; $('#search').value = '';
          $('#category-filters').querySelectorAll('button').forEach((button) => button.setAttribute('aria-pressed', String(!button.dataset.category)));
          loadActivities();
        },
      });
      return;
    }
    $('#activity-list').innerHTML = `<div class="card-grid">${data.items.map((activity) => `
      <article class="activity-card">
        <div class="badge-row">${categoryTag(activity.category)}${statusTag(activity.registration_status)}</div>
        <h3><a href="/activities/${activity.id}">${escapeHTML(activity.title)}</a></h3>
        <p class="card-club">${escapeHTML(activity.club_name)}</p>
        <p class="card-description">${escapeHTML(activity.description)}</p>
        <ul class="card-meta"><li>${icon('calendar')}<span>${escapeHTML(formatRange(activity.starts_at, activity.ends_at))}</span></li>
          <li>${icon('pin')}<span>${escapeHTML(activity.location)}</span></li></ul>
        <div class="card-footer"><span>剩余名额 <strong>${activity.remaining_capacity}</strong> 人</span><a href="/activities/${activity.id}" aria-label="查看${escapeHTML(activity.title)}详情">查看详情 ${icon('arrow')}</a></div>
      </article>`).join('')}</div>`;
    renderPagination($('#pagination'), data, (page) => { state.page = page; loadActivities(); });
  } catch (error) {
    if (error.name === 'AbortError' || current !== requestController) return;
    $('#results-count').textContent = '活动暂时无法加载';
    renderState($('#activity-list'), { kind: 'error', title: '加载失败', message: error.message, action: '重新加载', onAction: loadActivities });
  }
}

$('#search-form').addEventListener('submit', (event) => {
  event.preventDefault(); state.q = $('#search').value.trim(); state.page = 1; loadActivities();
});
// 分类和活动独立加载，单个请求失败不会让整个页面停留在空白。
loadCategories(); loadActivities();
