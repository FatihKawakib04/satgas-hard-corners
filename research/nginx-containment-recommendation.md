# Rekomendasi containment Nginx (belum diterapkan)

Status: READ-ONLY recommendation. Belum ada perubahan pada Nginx, database, laporan, atau file production.

## Konteks
Audit exposure publik menemukan file berikut dapat diakses melalui `https://satgas.ai.id/crypto/riset/...` meskipun tidak ditautkan dari halaman:
- `.translate/*.json`
- `*.id.bak`
- `*.md`
- `data/harga.csv`

Directory listing sudah 403 (`autoindex off`), tetapi `try_files $uri $uri/ /crypto/index.html` membuat semua file yang ada dikembalikan 200.

## Rekomendasi (untuk diterapkan manual oleh Fatih)

Tambahkan blok di dalam `location /crypto/ { ... }` (file `/etc/nginx/sites-available/satgas.ai.id`), sebelum `try_files`:

```nginx
# Containment: tolak file mentah/backup yang tidak dimaksudkan publik
location ~* ^/crypto/riset/(?:\.translate/.*|.*\.id\.bak|.*\.md|data/harga\.csv)$ {
    return 404;
}
```

Atau, lebih ketat, whitelist hanya ekstensi yang dimaksud publik:

```nginx
location ~* ^/crypto/riset/.*\.(?:html|json|css|js|png|jpg|svg)$ { }
location ~* ^/crypto/riset/ { return 404; }
```

Catatan:
- `fakta.json` tetap harus accessible (dipakai nav "data" dan consumer).
- Jangan memblokir `/crypto/api/` (Postman collection sengaja publik).
- Setelah perubahan: `nginx -t` lalu reload dari SSH (bukan dari sesi agent).
- Pertimbangkan juga memindahkan `.bak`/`.translate` ke luar web root agar tidak bergantung pada Nginx.

## Status
Belum diterapkan. Menunggu persetujuan Fatih.
