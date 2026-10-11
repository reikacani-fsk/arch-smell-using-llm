using Warehouse.Data;
using Warehouse.Pricing;

namespace Warehouse.Stock;

public class StockLedger
{
    private readonly Database _db = new();
    private readonly PriceList _prices = new();

    public int Available(string sku) => int.Parse(_db.Read($"stock:{sku}") ?? "0");

    public decimal StockValue(string sku) => Available(sku) * _prices.PriceOf(sku);
}
