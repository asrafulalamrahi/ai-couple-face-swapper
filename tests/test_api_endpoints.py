"""
API Route Function Unit Tests
"""

import os
import unittest
import asyncio
from backend.antigravity_master_backend import (
    health_check,
    gallery,
    get_output_media,
    download_output,
    delete_image_endpoint,
    resize_image_for_memory,
    OUTPUT_DIR,
)
import numpy as np
import cv2


class TestApiRouteHandlers(unittest.TestCase):

    def test_health_check_handler(self):
        res = asyncio.run(health_check())
        self.assertEqual(res["status"], "healthy")
        self.assertIn("storage", res)
        self.assertIn("google_drive_connected", res)

    def test_gallery_handler(self):
        res = asyncio.run(gallery())
        self.assertIn("outputs", res)
        self.assertIn("count", res)

    def test_output_and_delete_handlers(self):
        test_file = "test_handler_demo.jpg"
        test_path = OUTPUT_DIR / test_file
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        cv2.imwrite(str(test_path), img)

        # Test get_output_media
        media_resp = asyncio.run(get_output_media(test_file))
        self.assertEqual(media_resp.media_type, "image/jpeg")

        # Test download_output
        dl_resp = asyncio.run(download_output(test_file))
        self.assertEqual(dl_resp.media_type, "image/jpeg")

        # Test delete endpoint
        del_resp = asyncio.run(delete_image_endpoint(test_file))
        self.assertEqual(del_resp["status"], "success")
        self.assertFalse(test_path.exists())

    def test_resize_image_for_memory(self):
        # Create a large 2000x3000 mock image
        large_img = np.zeros((3000, 2000, 3), dtype=np.uint8)
        resized = resize_image_for_memory(large_img, max_dim=1280)
        h, w = resized.shape[:2]
        self.assertEqual(max(h, w), 1280)
        self.assertLess(h * w, 3000 * 2000)


if __name__ == "__main__":
    unittest.main()
