# Prompt: build a portable MongoDB e-commerce project

Create a small Node.js project using the official `mongodb` driver.

Requirements:

1. Read the connection exclusively from `MONGODB_URI` and the database name
   from `MONGODB_DATABASE`. Do not branch on whether the server is MongoDB or
   Azure DocumentDB.
2. Create one process-wide `MongoClient` and reuse its connection pool.
3. Seed deterministic e-commerce data into these referenced collections:
   `customers`, `products`, `orders`, `order_items`, and `inventory`.
4. Add indexes for the fields used by filters and joins.
5. Implement and verify:
   - a filtered and sorted `find()` query;
   - a customer/order summary using `$group` and `$lookup`;
   - an order-detail query joining orders, customers, and order items;
   - a product/inventory query using `$lookup`.
6. Make query output deterministic by projecting away `_id` and adding stable
   sort keys.
7. Add an automated verification command that asserts exact results.
8. First run everything against MongoDB 7. Then run the unchanged source
   against Azure DocumentDB by changing only `MONGODB_URI`.
9. Save each endpoint's query output separately and byte-compare them.

Do not hardcode credentials, disable TLS in source, or add database-specific
conditionals.
