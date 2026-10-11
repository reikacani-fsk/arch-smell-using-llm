namespace Shop.Core.Customers;

public class Customer
{
    public int Id { get; init; }
    public string Email { get; init; } = "";
}

public class CustomerRepository
{
    private readonly Dictionary<int, Customer> _customers = new();

    public void Add(Customer customer) => _customers[customer.Id] = customer;

    public Customer? Find(int id) => _customers.GetValueOrDefault(id);
}
