using Warehouse.Data;
using Warehouse.Pricing;
using Warehouse.Shipping;
using Warehouse.Stock;

namespace Warehouse.Orders;

public class OrderHandler
{
    private readonly Database _db = new();
    private readonly PriceList _prices = new();
    private readonly StockLedger _stock = new();
    private readonly Shipper _shipper = new();

    public int Place(string sku, int quantity)
    {
        if (_stock.Available(sku) < quantity || !_shipper.CanShip(sku, quantity)) return -1;
        var id = Random.Shared.Next();
        _db.Write($"order:{id}", $"{sku};{quantity};{_prices.PriceOf(sku) * quantity}");
        _shipper.Ship(id);
        return id;
    }

    public string? Find(int id) => _db.Read($"order:{id}");
}
