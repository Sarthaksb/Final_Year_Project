import cv2
import numpy as np

def test_image_quality():
    # 1. Create a perfectly smooth (blurry) image
    smooth_img = np.zeros((300, 300, 3), dtype=np.uint8)
    smooth_img.fill(128) # Gray
    
    gray_smooth = cv2.cvtColor(smooth_img, cv2.COLOR_BGR2GRAY)
    lap_var_smooth = cv2.Laplacian(gray_smooth, cv2.CV_64F).var()
    print(f"Smooth image blur score (should be ~0): {lap_var_smooth}")
    assert lap_var_smooth < 20, "Smooth image should be detected as blurry (reject)"
    
    # 2. Create a sharp image (random noise)
    sharp_img = np.random.randint(0, 256, (300, 300, 3), dtype=np.uint8)
    gray_sharp = cv2.cvtColor(sharp_img, cv2.COLOR_BGR2GRAY)
    lap_var_sharp = cv2.Laplacian(gray_sharp, cv2.CV_64F).var()
    print(f"Sharp image blur score (should be high): {lap_var_sharp}")
    assert lap_var_sharp > 100, "Sharp image should pass blur check"
    
    # 3. Create a dark image
    dark_img = np.zeros((300, 300, 3), dtype=np.uint8)
    dark_img.fill(10) # Very dark
    gray_dark = cv2.cvtColor(dark_img, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray_dark)
    print(f"Dark image brightness (should be 10): {brightness}")
    assert brightness < 20, "Dark image should be rejected"
    
    print("All image quality checks passed!")

if __name__ == "__main__":
    test_image_quality()
