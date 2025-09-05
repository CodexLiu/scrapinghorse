import modal

image = (
    modal.Image.debian_slim(python_version="3.12") \
    .uv_pip_install("fastapi[standard]", "modal", "slowapi", "requests") \
    .add_local_python_source(
        "v1.schemas", "v1.routes", "v1.modal_config", "v1.auth", "v1.rate_limiter"
    )
)

secrets = [
    modal.Secret.from_name("ScrapingHorse"),
]

app = modal.App(
    name="scraping-horse-gateway",
    image=image,
    secrets=secrets,
)