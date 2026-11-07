# How the smells of rkacani/bookstore emerged: LLM vs ground truth

Rate each answer, e.g. 2 = right and complete, 1 = partly right, 0 = wrong or missing.

## dense-structure

**Verdict:** correct

**Expected commit:** 3c965910f7 (step 21)

**LLM's commit:** 3c965910f7 (step 21)

### How

**Ground truth:** The dependencies between the namespaces grow step by step (17 dependencies between 8 namespaces after step 20, average degree 4.25). Step 21 adds Reporting, which depends on all 8 other namespaces: 25 dependencies between 9 namespaces, average degree 5.6 > 5.

**LLM:** I traced the namespace edges from the `using Bookstore.*` directives at each commit. The graph grew step by step. c234c7eee4 (shipping) brought in Orders->Billing, Orders->Catalog, Shipping->Customers and Shipping->Orders. a86bbbb882 added Billing->Orders through InvoiceService listing order lines. ca5b8bd971 (emails) added Customers->Notifications, Orders->Notifications and Shipping->Notifications. 4143cc872d (admin console) added Admin->Catalog and Admin->Customers. e2f30f57f6 added Integration->Orders. 1839acf54d (loyalty pricing) added Orders->Customers. 10a633cd5d added Notifications->Catalog. bfc2573685 added Admin->Notifications and Admin->Orders. 45ae161a74 briefly removed Billing->Orders by passing order data to billing as plain values. ce7435fa0a added Admin->Billing and Admin->Shipping. b117c1ad36 brought Billing->Orders back through PaymentService.Settle, which looks up and updates the Order. 146ae038ea's CartService repeated edges that already existed. At 3c965910f7~1 there were 17 distinct edges among 8 namespaces, an average degree of 4.25, which is below the density threshold. The edge count never went higher before that, so the smell was never present earlier. 3c965910f7 ('Add management dashboard') added the Reporting namespace with eight per-area report classes (CatalogReport, CustomerReport, OrderReport, RevenueReport, ShipmentReport, EmailReport, PartnerReport, AdminReport). Each one depends on a different namespace, which added 8 edges and a 9th component: 25 edges over 9 components gives the reported average degree of 5.56. The analyzed commit 9a6634f70f only changed method bodies in InvoiceService, PaymentService and OrderService and added no edges, so the smell is unchanged.

**LLM's timeline:**

- c234c7eee4 (step 5): Shipping added. Edges at this commit: Orders->Billing, Orders->Catalog, Shipping->Customers, Shipping->Orders.
- a86bbbb882 (step 6): InvoiceService uses Orders to list order lines, adding Billing->Orders.
- ca5b8bd971 (step 8): Welcome, order and shipping emails add Customers/Orders/Shipping -> Notifications.
- 4143cc872d (step 9): Admin console adds Admin->Catalog and Admin->Customers.
- e2f30f57f6 (step 10): PartnerApi adds Integration->Orders.
- 1839acf54d (step 12): Loyalty discount pricing adds Orders->Customers.
- 10a633cd5d (step 13): RecommendationBlock adds Notifications->Catalog.
- bfc2573685 (step 14): Admin order and newsletter commands add Admin->Orders and Admin->Notifications.
- 45ae161a74 (step 15): Billing->Orders is temporarily removed by passing plain values.
- ce7435fa0a (step 17): Admin shipment and invoice commands add Admin->Shipping and Admin->Billing, so Admin now depends on 6 namespaces.
- b117c1ad36 (step 20): PaymentService brings Billing->Orders back, a two-way link with Orders->Billing (17 edges among 8 namespaces).
- 3c965910f7 (step 21): Reporting namespace with 8 report classes adds 8 outgoing edges, one to every other namespace (25 edges over 9 components, average degree 5.56), and the smell appears.

**Rating (how):** 

### Why it is a problem

**Ground truth:** Nearly every namespace depends on several others, so there is no layering left that tells where a change stops.

**LLM:** 

**Rating (why):** 

## god-admin

**Verdict:** correct

**Expected commit:** ce7435fa0a (step 17)

**LLM's commit:** ce7435fa0a (step 17)

### How

**Ground truth:** Admin is created in step 9 with 17 classes (one command class per action), grows to 25 classes in step 14 and to 32 in step 17, more than the 30 classes Designite allows.

**LLM:** 4143cc872d created Bookstore.Admin with the AdminCommand base class, AdminConsole and one class per command for the catalog (8 commands) and customers (7 commands), 17 classes in total. bfc2573685 added OrderCommands.cs (5 commands) and NewsletterCommands.cs (3 commands), which brought it to 25 classes. ce7435fa0a added ShippingCommands.cs (4 commands) and InvoiceCommands.cs (3 commands), which brought it to 32 classes. That is over the class-count threshold, so the smell appears in this commit; at its parent the component had 25 classes. No later commit touched src/Bookstore/Admin, so the smell is still present at 9a6634f70f.

**LLM's timeline:**

- 4143cc872d (step 9): Admin component created with AdminCommand, AdminConsole and 15 catalog/customer command classes (17 classes)
- bfc2573685 (step 14): Added 5 order commands and 3 newsletter commands (25 classes)
- ce7435fa0a (step 17): Added 4 shipping commands and 3 invoice commands (32 classes); the threshold is crossed

**Rating (how):** 

### Why it is a problem

**Ground truth:** Every new admin action adds another class to the same namespace, which now mixes commands for the catalog, customers, orders, newsletters, shipments and invoices.

**LLM:** Bookstore.Admin keeps one command class for every operation of every other module: Catalog, Customers, Orders, Billing, Notifications and Shipping. It therefore depends on almost the whole system, and any feature change anywhere also means changing Admin. Admin commands for each module could not be owned, tested or reused separately, and the component keeps growing with each new feature.

**Rating (why):** 

## cycle-orders-billing

**Verdict:** correct

**Expected commit:** b117c1ad36 (step 20), first emerged in a86bbbb882 (step 6)

**LLM's commit:** b117c1ad36 (step 20)

### How

**Ground truth:** Orders has depended on Billing since step 3 (CheckoutService calls InvoiceService). In step 6 InvoiceService.CreateFor starts taking an Order and reading its OrderLines, so Billing depends on Orders and the cycle appears. Step 15 removes it again: InvoiceService gets plain values. In step 20 the new Billing.PaymentService loads the Order through OrderRepository to mark it paid, which closes the cycle again.

**LLM:** eaa567433e added Orders.CheckoutService, which depends on Billing.InvoiceService and Invoice (Orders -> Billing). At first, Billing only took plain values. a86bbbb882 changed InvoiceService.CreateFor to take an Order and read its OrderLines and OrderStatus ('using Bookstore.Orders'). That created a first Billing <-> Orders cycle. 45ae161a74 ('Pass order data to billing as plain values') removed the cycle: CreateFor went back to (orderId, amount, lines) and the Orders import was dropped, so from 45ae161a74 through 146ae038ea Billing did not depend on Orders. b117c1ad36 added Billing.PaymentService, which uses OrderRepository, Order, OrderLine and OrderStatus to mark orders as paid. That brought back Billing -> Orders while CheckoutService still had Orders -> Billing, so the cycle came back. 9a6634f70f only added a check inside PaymentService.Settle (return early if the invoice is already paid) and kept the cycle.

**LLM's timeline:**

- eaa567433e (step 3): CheckoutService (Orders) starts calling Billing.InvoiceService: Orders -> Billing
- a86bbbb882 (step 6): InvoiceService.CreateFor takes an Order and walks its OrderLines: Billing -> Orders; the first cycle appears
- 45ae161a74 (step 15): Billing gets plain values instead of Order; the cycle is removed
- b117c1ad36 (step 20): PaymentService added in Billing; it reads and updates Orders' OrderRepository/Order/OrderStatus, so the cycle comes back
- 9a6634f70f (step 22): PaymentService.Settle tidied up; the dependency on Orders remains

**Rating (how):** 

### Why it is a problem

**Ground truth:** Billing and Orders can no longer be built, tested or changed in isolation: a change to the order model can break settling invoices, and a change to invoicing can break checkout.

**LLM:** Checkout in Orders creates invoices, and payment in Billing reaches back into OrderRepository and sets Order.Status, so neither module can be built, tested or changed without the other. The team had already broken this cycle once in 45ae161a74 by passing plain values. PaymentService brings back the same coupling, so a change to Order or OrderLine (for example, how totals are computed) now affects Billing's payment logic as well.

**Rating (why):** 

## unstable-customers

**Verdict:** correct

**Expected commit:** 10a633cd5d (step 13)

**LLM's commit:** 10a633cd5d (step 13)

### How

**Ground truth:** Customers has depended on Notifications since step 8 (CustomerService sends the welcome email through EmailSender); then Notifications depended on nothing and was maximally stable. In step 13 Notifications gets RecommendationBlock, which reads books from Catalog. Notifications now has an outgoing dependency and becomes less stable than Customers. No file of Customers changed in that commit.

**LLM:** ca5b8bd971 added the Notifications component (EmailSender, EmailTemplate). In the same commit Customers.CustomerService started using EmailSender to send welcome mails, so Customers -> Notifications. At that point Notifications had no outgoing dependencies (instability 0), so the dependency was not unstable. 10a633cd5d ('Recommend books at the end of every email') added RecommendationBlock, which uses Bookstore.Catalog, and attached it to EmailSender. Notifications then had efferent coupling and could become less stable than Customers. Customers is used by many classes (Admin customer commands, OrderService, CartService, Shipping.AddressLookup and later reporting) and depends only on Notifications. Notifications also gained dependents afterwards (Admin newsletter commands in bfc2573685, EmailReport in 3c965910f7). How the tool weights the coupling is not visible: if you count only namespaces, Notifications does not come out less stable. What the history does show is that the smell could not exist before 10a633cd5d, because Notifications had instability 0 until then.

**LLM's timeline:**

- ca5b8bd971 (step 8): Notifications introduced; CustomerService depends on EmailSender (Customers -> Notifications)
- 10a633cd5d (step 13): EmailSender gets a RecommendationBlock that depends on Catalog, so Notifications becomes unstable

**Rating (how):** 

### Why it is a problem

**Ground truth:** Customers, which Orders, Shipping, Admin and later Reporting rely on, depends on Notifications, which now changes whenever the catalog changes.

**LLM:** Customers is a core module that orders, shipping and admin depend on. Through CustomerService it is tied to EmailSender, whose behaviour keeps changing, for example the catalog-based recommendation footer. Changes to email layout or recommendations can therefore ripple into customer registration and into everything that depends on Customers.

**Rating (why):** 

## ai-integration

**Verdict:** correct

**Expected commit:** a62b06d0cf (step 16)

**LLM's commit:** a62b06d0cf (step 16)

### How

**Ground truth:** Integration is created in step 10 with an explicit API: PartnerApi.ExportOrders, ImportOrder and CancelOrder. Step 16 makes them private and adds PartnerApi.Handle(string command, object payload) as the only public method of the component's 5 classes.

**LLM:** e2f30f57f6 added Bookstore.Integration with PartnerApi exposing three typed public methods: ExportOrders(), ImportOrder(PartnerOrder) and CancelOrder(int). a62b06d0cf ('Route all partner calls through one Handle entry point') made these methods private. It added a single public Handle(string command, object payload), which switches on strings like "export-orders", "import-order" and "cancel-order" and casts the payload. Since then, PartnerApi's only public members are its constructor and Handle. No later commit changed the Integration folder.

**LLM's timeline:**

- e2f30f57f6 (step 10): PartnerApi added with three explicit, typed public operations
- a62b06d0cf (step 16): Operations made private behind a single Handle(string, object) dispatcher

**Rating (how):** 

### Why it is a problem

**Ground truth:** Clients of PartnerApi can no longer see which operations exist or what payload each needs; a wrong command or payload type only fails at run time.

**LLM:** Callers of the partner integration can no longer see from the interface that it exports, imports and cancels orders, or which payload type each command needs. A wrong command string or a payload of the wrong type (PartnerOrder vs int) only fails at runtime through a cast or the 'unknown-command' branch. The compiler no longer checks the contract, and the dependencies of each operation are hidden.

**Rating (why):** 

## sf-orders-pricing

**Verdict:** too_early

**Expected commit:** 146ae038ea (step 19)

**LLM's commit:** 1839acf54d (step 12)

### How

**Ground truth:** Pricing is split between Catalog (PriceList) and Customers (LoyaltyProgram). Step 12 adds OrderService.QuoteFor, which combines both, once. Step 19 adds CartService.PreviewTotal, which combines them again: the concern is now realized in two places and Designite reports it (one method alone is not enough).

**LLM:** Both classes date from the initial commit dbccd6ee4a. Catalog.PriceList provides PriceOf(isbn), and Customers.LoyaltyProgram provides DiscountFor(customerId) alongside AddPoints. Neither file changed afterwards. The pricing concern became scattered in 1839acf54d ('Quote order prices with the loyalty discount'): OrderService (Orders) imported Bookstore.Customers and added QuoteFor, which combines PriceList.PriceOf with LoyaltyProgram.DiscountFor. The concern of computing what a customer pays is thereby spread over Catalog, Customers and Orders. Before this commit, Orders used only PriceList. 146ae038ea made it worse by adding CartService.PreviewTotal, which repeats the same price-times-discount calculation with PriceList and LoyaltyProgram.

**LLM's timeline:**

- dbccd6ee4a (step 1): PriceList (Catalog) and LoyaltyProgram with DiscountFor (Customers) created
- 1839acf54d (step 12): OrderService.QuoteFor combines PriceList and LoyaltyProgram; the pricing concern is now split across components
- 146ae038ea (step 19): CartService.PreviewTotal repeats the same price + loyalty discount calculation

**Rating (how):** 

### Why it is a problem

**Ground truth:** Computing a discounted price needs Catalog and Customers together, and the rule is repeated in Orders, so a change to discounts has to be made in several places.

**LLM:** The final price of a book for a customer is defined in three places: list prices in Catalog, discount tiers in Customers, and the combining formula duplicated in OrderService.QuoteFor and CartService.PreviewTotal. A pricing change such as a new discount rule, promotions or a different rounding means editing several components, and the copies can easily drift apart.

**Rating (why):** 

## unstable-orders

**Verdict:** correct

**Expected commit:** b117c1ad36 (step 20), first emerged in a86bbbb882 (step 6)

**LLM's commit:** b117c1ad36 (step 20)

### How

**Ground truth:** It comes with the cycle and emerges through Billing's files. Orders has depended on Billing since step 3; then Billing depended on nothing and was maximally stable. When Billing starts depending on Orders (InvoiceService in step 6; PaymentService in step 20, which loads the order and its lines), Billing refers to several Orders classes but is used by few classes, so it becomes less stable than Orders, which shipping, the partner API and the admin commands use. Step 15 removes Billing's dependency and with it the smell. No file of Orders changed in step 20.

**LLM:** Orders has depended on Billing's Invoice and InvoiceService since eaa567433e (CheckoutService creates invoices). From 45ae161a74 on, Billing had no outgoing dependencies at all: InvoiceService took plain values. With instability 0, Billing could not be less stable than Orders. An earlier period in which Billing depended on Orders, from a86bbbb882 until 45ae161a74, may have produced the same smell, but that was removed in 45ae161a74. b117c1ad36 added Billing.PaymentService, which depends on OrderRepository, Order, OrderLine and OrderStatus. This gave Billing efferent coupling and raised its instability, so the existing Orders -> Billing dependency (Invoice, InvoiceService) now points at a less stable component. 9a6634f70f changed InvoiceService and PaymentService without removing this dependency.

**LLM's timeline:**

- eaa567433e (step 3): CheckoutService in Orders depends on Billing's Invoice and InvoiceService
- a86bbbb882 (step 6): InvoiceService starts depending on Orders (earlier period of Billing instability)
- 45ae161a74 (step 15): Billing's dependency on Orders removed; Billing becomes maximally stable
- b117c1ad36 (step 20): PaymentService makes Billing depend on Orders again, so Billing becomes less stable than Orders

**Rating (how):** 

### Why it is a problem

**Ground truth:** Orders, which much of the shop relies on, depends on Billing, which now has to change along with the order model, so changes can ripple from Orders into Billing and back.

**LLM:** Orders is central: admin, shipping, integration, billing and reporting depend on it. Through CheckoutService it relies on InvoiceService.CreateFor and Invoice, in a Billing module that now changes along with order and payment logic. Changes in Billing's invoice API spread into checkout and from there to the many dependents of Orders.

**Rating (why):** 

## fc-shipping

**Verdict:** correct

**Expected commit:** daf6018e1e (step 18)

**LLM's commit:** daf6018e1e (step 18)

### How

**Ground truth:** Up to step 17 all classes of Shipping are connected through Shipment and ShipmentService; gift wrapping (step 11) is attached to Shipment. Step 18 adds returns (ReturnRequest, ReturnDesk) and pickup points (PickupPoint, PickupPointDirectory) as two groups that use neither each other nor the shipment classes: 3 groups in 10 classes, LCC 0.3 > 0.2.

**LLM:** c234c7eee4 created Shipping around ShipmentService, Shipment, Carrier and AddressLookup. ca5b8bd971 added ShippingNotifier, which ShipmentService uses, and a9caeed6c6 added GiftWrap, which Shipment and ShipmentService use. Up to then all classes formed one connected cluster. daf6018e1e ('Add returns and pickup points') put two unrelated features into the same namespace: PickupPoint with PickupPointDirectory, and ReturnDesk with ReturnRequest. ReturnRequest only stores a ShipmentId int, and neither pair uses nor is used by the shipment classes. The component now has three independent class groups (LCC 0.3).

**LLM's timeline:**

- c234c7eee4 (step 5): Shipping created with ShipmentService, Shipment, Carrier, AddressLookup
- ca5b8bd971 (step 8): ShippingNotifier added and used by ShipmentService (same cluster)
- a9caeed6c6 (step 11): GiftWrap added and used by Shipment and ShipmentService (same cluster)
- daf6018e1e (step 18): Unconnected PickupPoint/PickupPointDirectory and ReturnDesk/ReturnRequest features added

**Rating (how):** 

### Why it is a problem

**Ground truth:** Shipping now holds three unrelated features, so changes to returns or pickup points touch the same component as shipping itself, and none of them can be reused on its own.

**LLM:** Returns handling, the pickup-point directory and outbound shipment creation are separate features with no code links between them, yet they share one component. Work on returns or pickup points touches and redeploys the shipping module that admin commands and reporting depend on. The namespace no longer tells readers what it is responsible for, which makes separate ownership of these features harder.

**Rating (why):** 

