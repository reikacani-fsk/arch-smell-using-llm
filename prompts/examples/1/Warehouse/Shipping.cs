using Warehouse.Data;
using Warehouse.Pricing;
using Warehouse.Stock;

namespace Warehouse.Shipping;

public class Shipper
{
    private readonly Database _db = new();
    private readonly PriceList _prices = new();
    private readonly StockLedger _stock = new();

    public bool CanShip(string sku, int quantity) => _stock.Available(sku) >= quantity;

    public decimal InsuredValue(string sku, int quantity) => quantity * _prices.PriceOf(sku);

    public void Ship(int orderId) => _db.Write($"shipped:{orderId}", DateTime.UtcNow.ToString("O"));
}
