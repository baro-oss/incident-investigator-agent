// i18n.js — client-side translations (vi default + en)
// Quy ước: giữ acronym (MCP, LLM, API, SSE, HMAC...), dịch phần còn lại.
(function () {
  var TRANSLATIONS = {
    vi: {
      // ── Nav groups ──
      'nav.group.investigate': 'Điều tra',
      'nav.group.config': 'Cấu hình',
      'nav.group.observe': 'Quan sát',
      'nav.group.admin': 'Quản trị',
      // ── Nav items ──
      'nav.investigations': 'Cuộc điều tra',
      'nav.trigger': 'Kích hoạt',
      'nav.chat': 'Trò chuyện',
      'nav.demo': 'Chế độ demo',
      'nav.projects': 'Dự án',
      'nav.mcp': 'Đăng ký MCP',
      'nav.channels': 'Kênh thông báo',
      'nav.tools': 'Công cụ',
      'nav.catalog': 'Danh mục giả thuyết',
      'nav.scheduled': 'Lịch định kỳ',
      'nav.health': 'Tình trạng',
      'nav.cost': 'Chi phí',
      'nav.eval': 'Đánh giá',
      'nav.metrics': 'Số liệu trực tiếp',
      'nav.users': 'Người dùng & Vai trò',
      'nav.tokens': 'API Tokens',
      'nav.apidocs': 'Tài liệu API',
      'nav.logout': 'Đăng xuất',
      // ── Lang toggle ──
      'lang.toggle': 'EN',
      // ── Page headers ──
      'page.investigations': 'Cuộc điều tra',
      'page.trigger': 'Kích hoạt điều tra',
      'page.projects': 'Dự án',
      'page.mcp': 'Đăng ký MCP',
      'page.channels': 'Kênh thông báo',
      'page.tools': 'Danh mục công cụ',
      'page.catalog': 'Trình sửa danh mục giả thuyết',
      'page.scheduled': 'Kích hoạt định kỳ',
      'page.health': 'Tình trạng hệ thống',
      'page.cost': 'Bảng chi phí',
      'page.eval': 'Kết quả đánh giá',
      'page.metrics': 'Số liệu trực tiếp',
      'page.users': 'Quản lý người dùng',
      'page.roles': 'Quản lý vai trò',
      'page.groups': 'Quản lý nhóm dự án',
      'page.tokens': 'API Tokens (xác thực webhook)',
      // ── Section titles ──
      'sec.llm_config': 'Cấu hình LLM',
      'sec.services': 'Dịch vụ',
      'sec.channels': 'Kênh thông báo',
      'sec.mcp_servers': 'MCP Servers',
      'sec.repos': 'Repo / Mã nguồn',
      'sec.recent_inv': 'Điều tra gần đây',
      'sec.trigger_config': 'Cấu hình điều tra',
      'sec.quick_guide': 'Hướng dẫn nhanh',
      'sec.curl_equiv': 'Lệnh curl tương đương',
      'sec.register_mcp': 'Đăng ký MCP Server mới',
      'sec.circuit_breaker': 'Circuit Breaker — LLM',
      'sec.queue': 'Hàng đợi điều tra',
      'sec.recurring': 'Sự cố lặp lại',
      'sec.run_eval': 'Chạy đánh giá mới',
      'sec.pricing_ref': 'Bảng giá tham chiếu (USD / 1M tokens)',
      'sec.create_project': 'Tạo dự án mới',
      'sec.create_user': 'Tạo người dùng mới',
      'sec.create_role': 'Tạo vai trò mới',
      'sec.create_group': 'Tạo nhóm mới',
      'sec.create_token': 'Tạo API token mới',
      'sec.create_trigger': 'Tạo lịch mới',
      'sec.add_entry': 'Thêm mục mới',
      'sec.usage_guide': 'Hướng dẫn sử dụng',
      // ── Common buttons ──
      'btn.add': 'Thêm',
      'btn.delete': 'Xóa',
      'btn.save': 'Lưu',
      'btn.cancel': 'Huỷ',
      'btn.update': 'Cập nhật',
      'btn.enable': 'Bật',
      'btn.disable': 'Tắt',
      'btn.manage': 'Quản lý →',
      'btn.new_trigger': '▶ Trigger mới',
      'btn.clear_filter': 'Xóa filter',
      'btn.filter': 'Lọc',
      'btn.reload': '↺ Tải lại',
      'btn.create_project': 'Tạo dự án',
      'btn.create_user': 'Tạo người dùng',
      'btn.create_role': 'Tạo vai trò',
      'btn.create_group': 'Tạo nhóm',
      'btn.create_token': 'Tạo token',
      'btn.start_inv': '▶ Bắt đầu điều tra',
      'btn.register_mcp': '+ Đăng ký',
      'btn.test_run': '▶ Chạy thử',
      'btn.test_run_open': '▼ Chạy thử',
      'btn.test_run_closed': '▶ Chạy thử',
      // ── Status badges ──
      'status.on': 'bật',
      'status.off': 'tắt',
      // ── Table headers ──
      'th.name': 'Tên',
      'th.project': 'Dự án',
      'th.service': 'Dịch vụ',
      'th.status': 'Trạng thái',
      'th.auth': 'Xác thực',
      'th.ping_result': 'Kết quả Ping',
      'th.root_cause': 'Root Cause',
      'th.rc_type': 'Root Cause Type',
      'th.interval': 'Chu kỳ',
      'th.last_run': 'Lần chạy cuối',
      'th.next_run': 'Lần chạy tiếp',
      'th.action': 'Hành động',
      'th.metric': 'Chỉ số',
      'th.samples': 'Mẫu',
      'th.last_seen': 'Lần cuối',
      'th.runs': 'Lần',
      'th.correct': 'Đúng',
      'th.rate': 'Tỷ lệ',
      'th.gate': 'Gate',
      'th.hallucination': 'Hallucination',
      'th.avg_steps': 'Avg Steps',
      'th.avg_tokens': 'Avg Tokens',
      'th.no_cache': 'Không cache',
      'th.with_cache': 'Có cache',
      'th.delta': 'Delta',
      // ── Form labels ──
      'lbl.domain': 'Miền',
      'lbl.project': 'Dự án',
      'lbl.service': 'Dịch vụ',
      'lbl.time_window': 'Khung thời gian',
      'lbl.mcp_name': 'Tên *',
      'lbl.auth_type': 'Kiểu xác thực',
      'lbl.header_name': 'Tên header',
      'lbl.api_key_value': 'Giá trị API Key',
      'lbl.params': 'Params:',
      // ── Project card ──
      'lbl.services_label': 'DỊCH VỤ',
      'lbl.history': 'Lịch sử',
      'lbl.inv_count_suffix': 'điều tra',
      // ── Detail page sidebar ──
      'lbl.steps': 'Số bước',
      'lbl.stop_reason': 'Lý do dừng',
      'lbl.confidence': 'Confidence',
      // ── Detail page ──
      'lbl.back_inv': '← Điều tra',
      'lbl.detail_link': 'Chi tiết →',
      'lbl.root_cause_lbl': 'Root Cause',
      'lbl.actions': 'Hành động',
      // ── Cost page ──
      'lbl.total_eval_tokens': 'Tổng Token Eval',
      'lbl.live_inv': 'Điều tra thực tế',
      'lbl.cache_writes': 'Ghi cache',
      'lbl.cache_reads': 'Đọc cache',
      'lbl.net_savings': 'Tiết kiệm ròng',
      'lbl.overhead_cost': 'Chi phí overhead',
      'lbl.input_tokens_billed': 'Token đầu vào tính phí',
      'lbl.est_cost': 'Chi phí ước tính',
      // ── Metrics page ──
      'lbl.all_services': 'Tất cả dịch vụ',
      // ── Index page ──
      'lbl.all_projects': 'Tất cả dự án',
      'lbl.all_confidence': 'Tất cả độ tin cậy',
      // ── Eval page ──
      'lbl.overall_rate': 'Tỷ lệ chính xác',
      'h3.correct_rate': 'Tỷ lệ đúng theo Scenario',
      'h3.avg_steps_recall': 'Bước TB & Recall@1',
      // ── Health page ──
      'lbl.errors_consec': 'Lỗi liên tiếp',
    },
    en: {
      // ── Nav groups ──
      'nav.group.investigate': 'Investigate',
      'nav.group.config': 'Configuration',
      'nav.group.observe': 'Observe',
      'nav.group.admin': 'Admin',
      // ── Nav items ──
      'nav.investigations': 'Investigations',
      'nav.trigger': 'Trigger',
      'nav.chat': 'Chat',
      'nav.demo': 'Demo Mode',
      'nav.projects': 'Projects',
      'nav.mcp': 'MCP Registry',
      'nav.channels': 'Channels',
      'nav.tools': 'Tools',
      'nav.catalog': 'Catalog Editor',
      'nav.scheduled': 'Scheduled',
      'nav.health': 'Health',
      'nav.cost': 'Cost',
      'nav.eval': 'Eval',
      'nav.metrics': 'Metrics Live',
      'nav.users': 'Users & Roles',
      'nav.tokens': 'API Tokens',
      'nav.apidocs': 'API Docs',
      'nav.logout': 'Logout',
      // ── Lang toggle ──
      'lang.toggle': 'VI',
      // ── Page headers ──
      'page.investigations': 'Investigations',
      'page.trigger': 'Trigger Investigation',
      'page.projects': 'Projects',
      'page.mcp': 'MCP Registry',
      'page.channels': 'Alert Channels',
      'page.tools': 'Tool Registry',
      'page.catalog': 'Hypothesis Catalog Editor',
      'page.scheduled': 'Scheduled Triggers',
      'page.health': 'System Health',
      'page.cost': 'Cost Dashboard',
      'page.eval': 'Eval Results',
      'page.metrics': 'Metrics Live',
      'page.users': 'Manage Users',
      'page.roles': 'Manage Roles',
      'page.groups': 'Manage Project Groups',
      'page.tokens': 'API Tokens (Webhook Auth)',
      // ── Section titles ──
      'sec.llm_config': 'LLM Config',
      'sec.services': 'Services',
      'sec.channels': 'Alert Channels',
      'sec.mcp_servers': 'MCP Servers',
      'sec.repos': 'Repo / Source',
      'sec.recent_inv': 'Recent Investigations',
      'sec.trigger_config': 'Investigation Config',
      'sec.quick_guide': 'Quick Guide',
      'sec.curl_equiv': 'Equivalent curl',
      'sec.register_mcp': 'Register New MCP Server',
      'sec.circuit_breaker': 'Circuit Breaker — LLM',
      'sec.queue': 'Investigation Queue',
      'sec.recurring': 'Recurring Incidents',
      'sec.run_eval': 'Run New Eval',
      'sec.pricing_ref': 'Pricing Reference (USD / 1M tokens)',
      'sec.create_project': 'Create New Project',
      'sec.create_user': 'Create New User',
      'sec.create_role': 'Create New Role',
      'sec.create_group': 'Create New Group',
      'sec.create_token': 'Create New API Token',
      'sec.create_trigger': 'Create New Schedule',
      'sec.add_entry': 'Add New Entry',
      'sec.usage_guide': 'Usage Guide',
      // ── Common buttons ──
      'btn.add': 'Add',
      'btn.delete': 'Delete',
      'btn.save': 'Save',
      'btn.cancel': 'Cancel',
      'btn.update': 'Update',
      'btn.enable': 'Enable',
      'btn.disable': 'Disable',
      'btn.manage': 'Manage →',
      'btn.new_trigger': '▶ New Trigger',
      'btn.clear_filter': 'Clear filter',
      'btn.filter': 'Filter',
      'btn.reload': '↺ Reload',
      'btn.create_project': 'Create Project',
      'btn.create_user': 'Create User',
      'btn.create_role': 'Create Role',
      'btn.create_group': 'Create Group',
      'btn.create_token': 'Create Token',
      'btn.start_inv': '▶ Start Investigation',
      'btn.register_mcp': '+ Register',
      'btn.test_run': '▶ Test Run',
      'btn.test_run_open': '▼ Test Run',
      'btn.test_run_closed': '▶ Test Run',
      // ── Status badges ──
      'status.on': 'On',
      'status.off': 'Off',
      // ── Table headers ──
      'th.name': 'Name',
      'th.project': 'Project',
      'th.service': 'Service',
      'th.status': 'Status',
      'th.auth': 'Auth',
      'th.ping_result': 'Ping Result',
      'th.root_cause': 'Root Cause',
      'th.rc_type': 'Root Cause Type',
      'th.interval': 'Interval',
      'th.last_run': 'Last Run',
      'th.next_run': 'Next Run',
      'th.action': 'Action',
      'th.metric': 'Metric',
      'th.samples': 'Samples',
      'th.last_seen': 'Last Seen',
      'th.runs': 'Runs',
      'th.correct': 'Correct',
      'th.rate': 'Rate',
      'th.gate': 'Gate',
      'th.hallucination': 'Hallucination',
      'th.avg_steps': 'Avg Steps',
      'th.avg_tokens': 'Avg Tokens',
      'th.no_cache': 'Without Caching',
      'th.with_cache': 'With Caching',
      'th.delta': 'Delta',
      // ── Form labels ──
      'lbl.domain': 'Domain',
      'lbl.project': 'Project',
      'lbl.service': 'Service',
      'lbl.time_window': 'Time Window',
      'lbl.mcp_name': 'Name *',
      'lbl.auth_type': 'Auth Type',
      'lbl.header_name': 'Header Name',
      'lbl.api_key_value': 'API Key Value',
      'lbl.params': 'Params:',
      // ── Project card ──
      'lbl.services_label': 'SERVICES',
      'lbl.history': 'History',
      'lbl.inv_count_suffix': 'investigation(s)',
      // ── Detail page sidebar ──
      'lbl.steps': 'Steps',
      'lbl.stop_reason': 'Stop Reason',
      'lbl.confidence': 'Confidence',
      // ── Detail page ──
      'lbl.back_inv': '← Investigations',
      'lbl.detail_link': 'Detail →',
      'lbl.root_cause_lbl': 'Root Cause',
      'lbl.actions': 'Actions',
      // ── Cost page ──
      'lbl.total_eval_tokens': 'Total Eval Tokens',
      'lbl.live_inv': 'Live Investigations',
      'lbl.cache_writes': 'Cache Writes',
      'lbl.cache_reads': 'Cache Reads',
      'lbl.net_savings': 'Net Savings',
      'lbl.overhead_cost': 'Overhead Cost',
      'lbl.input_tokens_billed': 'Input Tokens Billed',
      'lbl.est_cost': 'Estimated Cost',
      // ── Metrics page ──
      'lbl.all_services': 'All Services',
      // ── Index page ──
      'lbl.all_projects': 'All Projects',
      'lbl.all_confidence': 'All Confidence',
      // ── Eval page ──
      'lbl.overall_rate': 'Overall Rate',
      'h3.correct_rate': 'Correct Rate per Scenario',
      'h3.avg_steps_recall': 'Avg Steps & Recall@1',
      // ── Health page ──
      'lbl.errors_consec': 'Consecutive Failures',
    }
  };

  var _lang = 'vi';

  function applyLang(lang) {
    _lang = lang;
    var dict = TRANSLATIONS[lang] || TRANSLATIONS['vi'];
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var key = el.getAttribute('data-i18n');
      if (dict[key] !== undefined) {
        el.textContent = dict[key];
      }
    });
    var btn = document.getElementById('lang-toggle-btn');
    if (btn) {
      btn.textContent = dict['lang.toggle'] || (lang === 'vi' ? 'EN' : 'VI');
    }
    document.documentElement.lang = lang;
    // Refresh theme label text (language-aware)
    if (window._applyTheme) {
      window._applyTheme(localStorage.getItem('ia-theme') || 'light');
    }
  }

  function toggleLang() {
    var next = _lang === 'vi' ? 'en' : 'vi';
    localStorage.setItem('ia-lang', next);
    applyLang(next);
  }

  document.addEventListener('DOMContentLoaded', function () {
    var saved = localStorage.getItem('ia-lang') || 'vi';
    applyLang(saved);
  });

  window.toggleLang = toggleLang;
  window.applyLang = applyLang;
  window.i18n = function(key) {
    return (TRANSLATIONS[_lang] || TRANSLATIONS['vi'])[key] || key;
  };
})();
