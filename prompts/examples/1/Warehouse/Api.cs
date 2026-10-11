using Warehouse.Data;
using Warehouse.Orders;
using Warehouse.Pricing;
using Warehouse.Shipping;
using Warehouse.Stock;

namespace Warehouse.Api;

public class WarehouseController
{
    private readonly Database _db = new();
    private readonly PriceList _prices = new();
    private readonly StockLedger _stock = new();
    private readonly Shipper _shipper = new();
    private readonly OrderHandler _orders = new();

    public string Order(string sku, int quantity) => $"order {_orders.Place(sku, quantity)}";

    public string Quote(string sku, int quantity) =>
        $"{_prices.PriceOf(sku) * quantity} (in stock: {_stock.Available(sku)}, " +
        $"insured: {_shipper.InsuredValue(sku, quantity)}, last order: {_db.Read("last-order")})";
}
