import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class StorePage extends StatefulWidget {
  const StorePage({super.key});
  @override
  State<StorePage> createState() => _StorePageState();
}

class _StorePageState extends State<StorePage> {
  List _products = [];
  List _cart = [];
  double _cartTotal = 0;
  List _coupons = [];
  Map<String, dynamic>? _viewing;

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
        api.get('/api/v1/store/products'),
        api.get('/api/v1/store/cart'),
        api.get('/api/v1/store/coupons'),
      ]);
      setState(() {
        _products = (results[0]['products'] as List?) ?? (results[0] is List ? results[0] : []);
        _cart = (results[1]['items'] as List?) ?? [];
        _cartTotal = (results[1]['total_yuan'] ?? 0).toDouble();
        _coupons = (results[2]['coupons'] as List?) ?? [];
      });
    } catch (_) {}
  }

  Future<void> _addToCart(int pid) async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      await api.post('/api/v1/store/cart', {'product_id': pid});
      _loadData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已加入购物车')));
      }
    } catch (_) {}
  }

  Future<void> _createOrder() async {
    final api = context.read<ApiService>();
    api.setToken(context.read<AuthService>().token);
    try {
      await api.post('/api/v1/store/orders', {'address': 'Flutter订单'});
      _loadData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('下单成功')));
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('下单失败')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('助眠商城'), actions: [
        Stack(children: [
          IconButton(icon: const Icon(Icons.shopping_cart), onPressed: () => _showCart()),
          if (_cart.isNotEmpty) Positioned(right: 4, top: 4, child: Container(
            padding: const EdgeInsets.all(4),
            decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
            child: Text('${_cart.length}', style: const TextStyle(fontSize: 10)),
          )),
        ]),
      ]),
      body: GridView.count(crossAxisCount: 2, padding: const EdgeInsets.all(16),
        crossAxisSpacing: 12, mainAxisSpacing: 12,
        childAspectRatio: 0.7,
        children: _products.map((p) => GestureDetector(
          onTap: () => setState(() => _viewing = p),
          child: Card(
            child: Column(children: [
              Expanded(child: Center(child: Text(p['image'] ?? '🛍️', style: const TextStyle(fontSize: 48)))),
              Padding(
                padding: const EdgeInsets.all(12),
                child: Column(children: [
                  Text(p['name'] ?? '', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                    Text('¥${p['price_yuan'] ?? ''}', style: const TextStyle(color: Color(0xFF6C63FF), fontWeight: FontWeight.bold)),
                    IconButton(icon: const Icon(Icons.add_shopping_cart, size: 20), onPressed: () => _addToCart(p['id'])),
                  ]),
                ]),
              ),
            ]),
          ),
        )).toList(),
      ),
    );
  }

  void _showCart() {
    showModalBottomSheet(context: context, builder: (_) => Container(
      padding: const EdgeInsets.all(16),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Text('购物车', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        if (_cart.isEmpty) const Padding(padding: EdgeInsets.all(32), child: Text('购物车为空')),
        ..._cart.map((item) => ListTile(
          title: Text(item['product_name'] ?? ''),
          subtitle: Text('¥${item['price_yuan']} × ${item['quantity'] ?? 1}'),
        )),
        if (_cart.isNotEmpty) ...[
          const Divider(),
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Text('合计: ¥$_cartTotal', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            ElevatedButton(onPressed: () { Navigator.pop(context); _createOrder(); }, child: const Text('下单')),
          ]),
        ],
      ]),
    ));
  }
}
