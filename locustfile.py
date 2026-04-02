import random
import string

from locust import HttpUser, between, task


class ProductUser(HttpUser):
    wait_time = between(0.5, 2)

    @task(3)
    def list_products(self):
        self.client.get("/products")

    @task(2)
    def list_products_paginated(self):
        page = random.randint(1, 5)
        self.client.get(f"/products?page={page}&page_size=10")

    @task(1)
    def search_products(self):
        term = random.choice(["widget", "phone", "laptop", "async", "pro"])
        self.client.get(f"/products?search={term}")

    @task(1)
    def create_product(self):
        name = "Product-" + "".join(random.choices(string.ascii_lowercase, k=6))
        self.client.post(
            "/products",
            json={
                "name": name,
                "price": round(random.uniform(1.0, 999.99), 2),
                "description": f"Load test product {name}",
            },
        )
