import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class VipPage extends StatefulWidget {
  const VipPage({super.key});
  @override
  State<VipPage> createState() => _VipPageState();
}

class _VipPageState extends State<VipPage> {
  Map<String, dynamic>? _premium;
  String _billing = 'monthly';
  bool _payLoading = false;
  Map<String, dynamic>? _payOrder;
  List _payOrders = [];
  String? _referralCode;
  int _referralCount = 0;
  double _referralReward = 0;
  bool _showPayModal = false;

  final _tierFeatures = {
    'free': ['基础睡眠记录', 'AI助手(每日5次)', '白噪音基础', '每日任务'],
    'freeMissing': ['深度睡眠报告', '睡眠预测', '高级白噪音', '语音日记', '家庭共享'],
    'pro': ['无限AI对话', '高级白噪音引擎', '深度睡眠报告', '睡眠预测', '优先支持', '全部改善计划'],
    'premium': ['全部Pro功能', 'AI深度分析报告', '个性化睡眠教练', '语音日记', '高级睡眠故事', '健康数据同步', '家庭共享(5人)'],
  };

  final _compareRows = [
    {'name': '每日AI对话', 'free': '5次', 'pro': '无限', 'premium': '无限', 'highlight': true},
    {'name': '白噪音引擎', 'free': '基础', 'pro': '高级', 'premium': '全部', 'highlight': false},
    {'name': '睡眠报告', 'free': '基础', 'pro': '深度', 'premium': 'AI深度', 'highlight': true},
    {'name': '睡眠预测', 'free': '✗', 'pro': '✓', 'premium': '✓', 'highlight': false},
    {'name': '语音日记', 'free': '✗', 'pro': '✗', 'premium': '✓', 'highlight': false},
    {'name': '睡眠故事', 'free': '3个', 'pro': '全部', 'premium': '全部+定制', 'highlight': false},
    {'name': '改善计划', 'free': '基础', 'pro': '全部', 'premium': 'AI定制', 'highlight': true},
    {'name': '健康数据同步', 'free': '✗', 'pro': '✗', 'premium': '✓', 'highlight': false},
    {'name': '家庭共享', 'free': '✗', 'pro': '✗', 'premium': '5人', 'highlight': false},
    {'name': '优先客服', 'free': '✗', 'pro': '✓', 'premium': '✓', 'highlight': false},
    {'name': '商城折扣', 'free': '无', 'pro': '95折', 'premium': '9折', 'highlight': false},
  ];

  final _perks = [
    {'icon': '🎁', 'title': '专属折扣', 'desc': '助眠商城9折优惠'},
    {'icon': '🚀', 'title': '优先体验', 'desc': '新功能抢先试用'},
    {'icon': '💎', 'title': '专属标识', 'desc': '尊贵会员身份'},
    {'icon': '🎫', 'title': '会员活动', 'desc': '定期线上讲座'},
  ];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final results = await Future.wait([
        api.get('/api/v1/premium/status'),
        api.get('/api/v1/payment/orders'),
      ]);
      setState(() {
        _premium = results[0];
        _payOrders = (results[1]['orders'] as List?) ?? [];
      });
    } catch (_) {}
  }

  Future<void> _loadReferral() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.get('/api/v1/referral/code');
      setState(() {
        _referralCode = data['code'];
        _referralCount = data['invite_count'] ?? 0;
        _referralReward = (data['reward_yuan'] ?? 0).toDouble();
      });
    } catch (_) {}
  }

  int _vipDaysLeft() {
    if (_premium != null && _premium!['tier'] != 'free' && _premium!['expires_at'] != null) {
      final diff = DateTime.parse(_premium!['expires_at']).difference(DateTime.now());
      return diff.inDays > 0 ? diff.inDays : 0;
    }
    return 0;
  }

  Future<void> _createOrder(String plan) async {
    setState(() => _payLoading = true);
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      final data = await api.post('/api/v1/payment/orders', {'plan_id': plan, 'method': 'wechat'});
      setState(() { _payOrder = data; _showPayModal = true; });
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('创建订单失败')));
      }
    }
    setState(() => _payLoading = false);
  }

  Future<void> _confirmPay() async {
    setState(() => _payLoading = true);
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      await api.post('/api/v1/payment/orders/${_payOrder!['order_id']}/pay', {'transaction_id': 'SIM${DateTime.now().millisecondsSinceEpoch}'});
      setState(() { _showPayModal = false; _payOrder = null; });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('支付成功！')));
      }
      _loadData();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('支付失败')));
      }
    }
    setState(() => _payLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    final tier = _premium?['tier'] ?? 'free';
    return Stack(children: [
      Scaffold(
        appBar: AppBar(title: const Text('会员中心')),
        body: RefreshIndicator(
          onRefresh: _loadData,
          child: ListView(padding: const EdgeInsets.all(16), children: [
            // Hero Banner
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                gradient: LinearGradient(colors: tier == 'premium' ? [const Color(0xFF2a1a3e), const Color(0xFF1a1a3e)] : tier == 'pro' ? [const Color(0xFF1a1a4e), const Color(0xFF1a2a4e)] : [const Color(0xFF1a1a3e), const Color(0xFF16213e)]),
              ),
              child: Row(children: [
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(tier == 'premium' ? '👑' : tier == 'pro' ? '⭐' : '🌱', style: const TextStyle(fontSize: 48)),
                  Text('${_premium?['tier_info']?['name'] ?? '免费版'}会员', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
                  Text(tier != 'free' ? '剩余${_vipDaysLeft()}天' : '升级解锁全部高级功能', style: const TextStyle(color: Colors.grey)),
                ])),
                if (tier == 'free')
                  Column(children: [
                    const Text('¥29', style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold)),
                    const Text('/月'),
                    const SizedBox(height: 8),
                    ElevatedButton(onPressed: () {}, child: const Text('立即升级')),
                  ]),
              ]),
            ),
            const SizedBox(height: 16),

            // Billing Toggle
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              ChoiceChip(label: const Text('月付'), selected: _billing == 'monthly', onSelected: (_) => setState(() => _billing = 'monthly')),
              const SizedBox(width: 8),
              ChoiceChip(label: const Text('年付 省35%'), selected: _billing == 'yearly', onSelected: (_) => setState(() => _billing = 'yearly')),
            ]),
            const SizedBox(height: 16),

            // Pricing Cards
            SingleChildScrollView(scrollDirection: Axis.horizontal, child: Row(children: [
              _pricingCard('🌱', '免费版', '0', '/永久', _tierFeatures['free']!, _tierFeatures['freeMissing']!, null),
              if (tier != 'premium')
                _pricingCard('⭐', '专业版', _billing == 'yearly' ? '16' : '29', '/月', _tierFeatures['pro']!, ['家庭共享'],
                    _billing == 'yearly' ? 'pro_yearly' : 'pro_monthly', recommended: true),
              _pricingCard('👑', '尊享版', _billing == 'yearly' ? '33' : '59', '/月', _tierFeatures['premium']!, [],
                  _billing == 'yearly' ? 'premium_yearly' : 'premium_monthly'),
            ])),
            const SizedBox(height: 16),

            // Feature Comparison
            Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
              const Text('📋 完整功能对比', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              ..._compareRows.map((r) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(children: [
                  Expanded(flex: 3, child: Text(r['name'] as String, style: const TextStyle(fontSize: 13))),
                  Expanded(flex: 2, child: Text(r['free'] as String, style: const TextStyle(fontSize: 13), textAlign: TextAlign.center)),
                  Expanded(flex: 2, child: Text(r['pro'] as String, style: TextStyle(fontSize: 13, color: r['highlight'] == true ? const Color(0xFF6C63FF) : null, fontWeight: r['highlight'] == true ? FontWeight.bold : null), textAlign: TextAlign.center)),
                  Expanded(flex: 2, child: Text(r['premium'] as String, style: TextStyle(fontSize: 13, color: r['highlight'] == true ? const Color(0xFF6C63FF) : null, fontWeight: r['highlight'] == true ? FontWeight.bold : null), textAlign: TextAlign.center)),
                ]),
              )),
            ]))),

            // Perks
            if (tier != 'free') ...[
              const SizedBox(height: 16),
              Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
                const Text('🎁 会员专属', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                Wrap(spacing: 8, children: _perks.map((p) => Chip(
                  avatar: Text(p['icon'] as String),
                  label: Text('${p['title']}: ${p['desc']}'),
                )).toList()),
              ]))),
            ],

            // Referral
            Card(child: Padding(padding: const EdgeInsets.all(16), child: Row(children: [
              const Text('🔗 邀请好友'),
              const Spacer(),
              OutlinedButton(onPressed: _loadReferral, child: const Text('查看')),
            ]))),
            if (_referralCode != null)
              Padding(padding: const EdgeInsets.all(8), child: Text('邀请码: $_referralCode · 已邀请 $_referralCount 人 · 奖励 ¥$_referralReward')),

            // Order History
            const SizedBox(height: 16),
            Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
              Row(children: [const Text('📄 订单记录', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)), const Spacer(), TextButton(onPressed: _loadData, child: const Text('刷新'))]),
              if (_payOrders.isEmpty) const Text('暂无订单', style: TextStyle(color: Colors.grey)),
              ..._payOrders.map((o) => ListTile(
                dense: true,
                title: Text('${o['order_no']} · ${o['tier']}', style: const TextStyle(fontSize: 13)),
                trailing: Text('¥${o['amount_yuan']}', style: TextStyle(color: o['status'] == 'paid' ? Colors.green : o['status'] == 'refunded' ? Colors.red : Colors.orange)),
              )),
            ]))),
          ]),
        ),
      ),

      // Pay Modal
      if (_showPayModal && _payOrder != null)
        GestureDetector(
          onTap: () => setState(() => _showPayModal = false),
          child: Container(color: Colors.black54, child: Center(
            child: Card(
              child: Container(width: 320, padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Text('💳', style: TextStyle(fontSize: 48)),
                Text(_payOrder!['plan_name'] ?? '', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                Text('¥${_payOrder!['amount_yuan']}', style: const TextStyle(fontSize: 36, fontWeight: FontWeight.bold)),
                Text('订单号: ${_payOrder!['order_no']}', style: const TextStyle(color: Colors.grey, fontSize: 12)),
                const SizedBox(height: 16),
                const Text('🔒 模拟支付环境', style: TextStyle(color: Colors.grey, fontSize: 12)),
                const SizedBox(height: 16),
                SizedBox(width: double.infinity, child: ElevatedButton(
                  onPressed: _payLoading ? null : _confirmPay,
                  child: Text(_payLoading ? '支付中...' : '确认支付 ¥${_payOrder!['amount_yuan']}'),
                )),
                TextButton(onPressed: () => setState(() => _showPayModal = false), child: const Text('取消')),
              ])),
            ),
          )),
        ),
    ]);
  }

  Widget _pricingCard(String icon, String name, String price, String period, List<String> features, List<String> missing, String? planId, {bool recommended = false}) {
    final tier = _premium?['tier'] ?? 'free';
    final isActive = (name == '免费版' && tier == 'free') || (name == '专业版' && tier == 'pro') || (name == '尊享版' && tier == 'premium');
    return Container(
      width: 200,
      margin: const EdgeInsets.symmetric(horizontal: 6),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(children: [
            if (recommended) Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(12), color: Colors.orange),
              child: const Text('🔥 推荐', style: TextStyle(color: Colors.white, fontSize: 12)),
            ),
            const SizedBox(height: 4),
            Text(icon, style: const TextStyle(fontSize: 40)),
            Text(name, style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: isActive ? const Color(0xFF6C63FF) : null)),
            Text.rich(TextSpan(children: [TextSpan(text: '¥$price', style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold)), TextSpan(text: period, style: const TextStyle(color: Colors.grey, fontSize: 14))])),
            const SizedBox(height: 12),
            ...features.map((f) => Row(children: [const Icon(Icons.check, size: 16, color: Colors.green), const SizedBox(width: 4), Expanded(child: Text(f, style: const TextStyle(fontSize: 12)))])),
            ...missing.map((f) => Row(children: [const Icon(Icons.close, size: 16, color: Colors.grey), const SizedBox(width: 4), Expanded(child: Text(f, style: const TextStyle(fontSize: 12, color: Colors.grey, decoration: TextDecoration.lineThrough)))])),
            const SizedBox(height: 12),
            if (planId != null)
              SizedBox(width: double.infinity, child: ElevatedButton(
                onPressed: _payLoading ? null : () => _createOrder(planId),
                child: Text(_payLoading ? '处理中...' : tier == (name == '专业版' ? 'pro' : 'premium') ? '续费' : '升级'),
              ))
            else if (isActive)
              OutlinedButton(onPressed: null, child: const Text('当前方案')),
          ]),
        ),
      ),
    );
  }
}
