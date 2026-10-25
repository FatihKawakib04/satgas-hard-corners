"""Tes dasar. Ganti dengan tes yang benar-benar menguji logika inti.

Ditulis dengan unittest supaya jalan tanpa memasang apa pun. pytest juga bisa
menjalankan berkas ini kalau nanti dipakai.
"""
import unittest


def tambah(a: int, b: int) -> int:
    return a + b


class TesDasar(unittest.TestCase):
    def test_tambah(self):
        self.assertEqual(tambah(2, 3), 5)
