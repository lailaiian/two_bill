# 0414改的 有兩次的閥值去做日期 但是好像沒啥用QAQ

import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
import pyzbar.pyzbar as pyzbar
from PIL import Image,ImageEnhance
import darknet
import darknet_me
import math
import re
import time
import pymysql
import shutil
from sklearn.cluster import KMeans
import time

def mysql_reset():
    conn = pymysql.connect(
        host = 'localhost',
        port = 3306,
        user = "root",
        passwd = "",
        db = "uitest",
        charset='utf8mb4')
    cur=conn.cursor()#獲取遊標
    sql_reset ="truncate table invoice"
    insert=cur.execute(sql_reset)
    cur.close()
    conn.commit()
    conn.close()

def mysql_connect(main,word_track,date,seller_number,buyer_number,total_amount, tax_free, tax_amount, rate, imagePath):
    conn = pymysql.connect(
        host = 'localhost',
        port = 3306,
        user = "root",
        password = "",
        db = "uitest")
        #charset='UTF8')
    #print (conn)
    #print (type(conn))
    cur=conn.cursor()#獲取遊標
    #fp = open(imagePath,"rb")  #不使用
    #img = fp.read()    #不使用
    #img_Contents = base64.b64encode(img)    #圖片轉碼 不使用
    #img_Contents = str(img_Contents,'utf-8')    #轉碼後再轉編utf8 不使用
    copy_image_to_htdocs(imagePath,main)
    #fp.close()

    #invDate = str(int(date[0:3])+1911)+"/"+date[-4:-2]+"/"+date[-2:-1]+date[-1] 本來有放出來 但我看似乎沒用到 就反掉了

    sql="INSERT INTO invoice(main, word_track, date, seller_number, buyer_number, total_amount, tax_free, tax_amount, rate, image)VALUES ("+"'" + main + "','"+ word_track + "','"+ date +"','" + seller_number +"','" + buyer_number +"','" + total_amount +"','" + tax_free +"','" + tax_amount +"','"+rate+"','" + "./img/" + main + ".jpg\')"
    insert=cur.execute(sql)
    cur.close()
    conn.commit()
    conn.close()
    print('sql執行成功')
def mysql_set_max_allowed_packet():
   data = ''
   with open(r"C:\xampp\mysql\bin\my.ini", 'r+') as f:
       for line in f.readlines():
           if(line.find('max_allowed_packet=1M') == 0):
               line = 'max_allowed_packet=100M' + "\n"
           data += line
   with open(r"C:\xampp\mysql\bin\my.ini", 'r+') as f:
      f.writelines(data)
def copy_image_to_htdocs(imagePath,main):
# 定义当前目录和目标路径
    destination = r'C:\xampp\htdocs\UI\img/'+str(main)+'.jpg'  # 替换为实际的目标路径

    # 复制文件到目标路径
    shutil.copy(imagePath, destination)

    # 删除原始文件
    #if os.path.exists(imagePath):
    #    os.remove(imagePath)
    #    print(f'{imagePath} 已成功删除。')
    #else:
    #    print(f'{imagePath} 文件不存在。')


def electronic_invoice(image_path, image_name):

    def process_left_half(image  ,image_file,artwork):
        #                切完彩邊  圖片路徑     原圖
        height, width = image.shape[:2]
        left_half = image[:, :width // 2]
        cropped = left_half[:, 10:width]
        # 轉為灰階
        gray_img = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)

        # 自適應二值化處理
        binary_image = cv2.adaptiveThreshold(gray_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 13, 3)
        # 腐蝕操作
        kernel = np.ones((3, 4), np.uint8)
        erosion = cv2.erode(binary_image, kernel, iterations=1)

        # 二值化處理
        _, thresh_image = cv2.threshold(erosion, 127, 255, cv2.THRESH_BINARY)

        # 計算水平投影
        horizontal_projection = np.sum(thresh_image, axis=1)

        segments = []
        is_segment = False
        start_row = 0
        max_length = 0
        max_segment = None  # 用於記錄最大段

        for row, value in enumerate(horizontal_projection):
            if value > 0 and not is_segment:
                # 段開始
                start_row = row
                is_segment = True
            elif value == 0 and is_segment:
                # 段結束
                end_row = row - 1
                is_segment = False
                segments.append((start_row, end_row))
                segment_length = end_row - start_row + 1
                # 更新最大段
                if segment_length > max_length:
                    max_length = segment_length
                    max_segment = (start_row, end_row)

        # 如果最後一段延伸到圖像底部，補充其結尾
        if is_segment:
            end_row = len(horizontal_projection) - 1
            segments.append((start_row, end_row))
            segment_length = end_row - start_row + 1
            if segment_length > max_length:
                max_segment = (start_row, end_row)

        # 合併距離很近的框
        merged_segments = []
        merge_threshold = 3  # 設置合併的距離閾值
        for segment in segments:
            if not merged_segments:
                merged_segments.append(segment)
            else:
                last_start, last_end = merged_segments[-1]
                current_start, current_end = segment
                # 如果當前段與上一段距離小於閾值，合併它們
                if current_start - last_end <= merge_threshold:
                    merged_segments[-1] = (last_start, current_end)
                else:
                    merged_segments.append(segment)

        # 找到最大段上方且高度符合條件的框
        segments_above = []
        if max_segment:
            max_start_row, _ = max_segment
            # 篩選出在最大段上方且高度符合條件的框
            segments_above = [
                (start_row, end_row) for start_row, end_row in merged_segments
                if end_row < max_start_row and 10 <= (end_row - start_row + 1) <= 150
            ]
            # 按結束行排序，選取上方的前 5 個框
            segments_above = sorted(segments_above, key=lambda x: x[1], reverse=True)[:5]

        # 在副本上繪製框
        drawn_image = artwork.copy()

        if max_segment:
            # 繪製最大段（紅框）
            start_row, end_row = max_segment
            cropped_red_box = image[start_row:end_row + 1, :]  # 裁剪紅框部
            cv2.rectangle(drawn_image, (0, start_row), (drawn_image.shape[1] - 1, end_row), (0, 255, 0), 2)

        for i, (start_row, end_row) in enumerate(segments_above):
            if i == 0 or i==2:
                continue  # 跳過第一個區間
            if i==1:
                cv2.rectangle(drawn_image, (0, start_row), (drawn_image.shape[1] - 1, end_row), (255, 0, 0), 2)
            if i==3:
                cv2.rectangle(drawn_image, (0, start_row), (drawn_image.shape[1] - 1, end_row), (0, 255, 255), 2)
            if i==4:
                cv2.rectangle(drawn_image, (0, start_row), (drawn_image.shape[1] - 1, end_row), (0, 165, 255), 2)

        save_dir = r"C:\seniorProject\LaiCode\two_bill\ele_output\finalImg"
        output_filename = os.path.join(save_dir, os.path.splitext(os.path.basename(image_file))[0] + "_processed.png")
        cv2.imwrite(output_filename, drawn_image)
        adjust_cropped_image(cropped_red_box, left_half, image_file, image)

        global finalpath
        finalpath = output_filename

    def colorful_edge(image):
        h, w = image.shape[:2]
        if h > 2000:
            image_2=image[int(h * 0.01):int(h * 0.5),:]
            gray = cv2.cvtColor(image_2, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (9, 9), 0)
            binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 13, 4)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            binary = cv2.dilate(binary, kernel)
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (9, 9), 0)
            binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 13, 4)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            binary = cv2.dilate(binary, kernel)

         # 取得影像大小
        (h2, w2) = binary.shape
        # 計算每一列的黑色像素數量
        search_range = int(w * 0.1)
        b = np.sum(binary == 0, axis=0)

        # 更新影像，僅保留上部分白色像素
        # 使用逐列迴圈處理，避免向量化索引錯誤
        for j in range(w2):
            binary[h2 - b[j]:, j] = 0

        if h > 2000:
             # 忽略前 15 個數據，從第 16 列開始尋找最小黑色像素數量對應的索引
            min_black_pixel_value = np.min(b[15:search_range])
            left_candidates = np.where(b[15:search_range] == min_black_pixel_value)[0] + 15  # 修正索引偏移
            left = left_candidates[-1] if len(left_candidates) > 0 else None
            # 找到左右邊界
            zero_indices = np.where(b[-search_range:] == 0)[0]
            if len(zero_indices) > 0:
                # 找第一段連續的 0
                first_segment = [zero_indices[0]]  # 記錄第一個 0 的區段
                for i in range(1, len(zero_indices)):
                    if zero_indices[i] == zero_indices[i - 1] + 1:  # 檢查是否連續
                        first_segment.append(zero_indices[i])
                    else:
                        break  # 一旦發現跳躍，停止
                # 取第一段 0 的中間索引
                mid_index = first_segment[len(first_segment) // 2]
            right =  w2- len(b[-search_range:])+mid_index  # 找右半邊最小值

        else:
            left = np.argmax(b < 10)
            right = w2 - np.argmax((b < 10)[::-1]) - 1
            left = max(0, left + 10)
            right = min(w2 - 1, right - 10)
        #改
        # 裁剪影像
        #改
        image[:, :left] = (255, 255, 255)
        image[:, right:] = (255, 255, 255)
        return image

    def adjust_cropped_image(cropped_image, original_image, image_file,images):
        if cropped_image is None or cropped_image.size == 0:
            return

        gray_cropped = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)

        binary_image = cv2.adaptiveThreshold(gray_cropped, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 13, 3)

        kernel = np.ones((3, 3), np.uint8)
        erosion = cv2.erode(binary_image, kernel, iterations=1)

        vertical_projection = np.sum(erosion, axis=0)
        h, w = erosion.shape
        start_col = None
        threshold = 5
        rectangles = []

        for col in range(w):
            if vertical_projection[col] > 0:
                if start_col is None:
                    start_col = col
            elif start_col is not None:
                rectangles.append((start_col, col))
                start_col = None

        merged_rectangles = []
        previous_start, previous_end = rectangles[0]

        for start, end in rectangles[1:]:
            if start - previous_end <= threshold:
                previous_end = end
            else:
                merged_rectangles.append((previous_start, previous_end))
                previous_start, previous_end = start, end

        merged_rectangles.append((previous_start, previous_end))
        padding = 10
        max_rectangle = max(merged_rectangles, key=lambda x: x[1] - x[0])
        max_start = max(0, max_rectangle[0] - padding)
        max_end = min(w, max_rectangle[1] + padding)

        largest_box_image = cropped_image[:, max_start:max_end]

        QRcord(largest_box_image, images, image_file)

    def QRcord(img, images, image_file):
        success_log_file = r'C:\seniorProject\LaiCode\two_bill\ele_output\out.txt'
        try:

            img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

            img_pil = ImageEnhance.Contrast(img_pil).enhance(5.0)
            img_pil = img_pil.convert('L')  # 灰度化

            barcodes = pyzbar.decode(img_pil)
            if not barcodes:
                raise ValueError("掃描結果為空")

            for barcode in barcodes:
                barcodeData = barcode.data.decode("utf-8")
                all_checks_passed = True

                el_number = barcodeData[:10]
                el_date = barcodeData[10:17]
                el_sales = barcodeData[21:29]
                el_total = barcodeData[29:37]
                el_buyserial = barcodeData[37:45]
                el_sellserial = barcodeData[45:53]

                if not re.match(r"^[A-Za-z]{2}\d{8}$", el_number):
                    all_checks_passed = False
                if not re.match(r"^\d{7}$", el_date):
                    all_checks_passed = False
                if not re.match(r"^[0-9A-Fa-f]{8}$", el_sales):
                    all_checks_passed = False
                if not re.match(r"^[0-9A-Fa-f]{8}$", el_total):
                    all_checks_passed = False
                if not re.match(r"^\d{8}$", el_buyserial):
                    all_checks_passed = False
                if not re.match(r"^\d{8}$", el_sellserial):
                    all_checks_passed = False

                if all_checks_passed:
                    with open(success_log_file, 'a', encoding='utf-8') as f:
                        f.write(f"完整條碼資料：{barcodeData}\n")
                        f.write(f"字軌號碼：{el_number}\n")
                        f.write(f"日期：{el_date}\n")
                        f.write(f"銷售額：{int(el_sales, 16)}\n")
                        f.write(f"總計額：{int(el_total, 16)}\n")
                        f.write(f"買方統一編號：{el_buyserial}\n")
                        f.write(f"賣方統一編號：{el_sellserial}\n")
                        f.write("-" * 50 + "\n")

                        global word_track, date, seller_number, buyer_number, total_amount, tax_free, tax_amount, rate, finalpath

                        a = int(el_sales, 16)
                        b = int(el_total, 16)

                        word_track = el_number
                        date = el_date
                        seller_number = el_sellserial
                        buyer_number = el_buyserial
                        total_amount = b

                        #改
                        if a == b:
                            tax_free = a
                            tax_amount = 0
                            rate = 0
                            #改
                            ex_image(images,image_file,step=2)
                        else:
                            tax_free = 0
                            tax_amount = a
                            rate = b - a

                else:
                    print("條碼錯誤啦")
                    raise ValueError("條碼資料未通過格式檢查")

        except ValueError as e:
            #改
            ex_image(images,image_file,step=1)

    def ex_image(images,image_file,step=1):
        global tax_amount, tax_free ,total_amount, rate
        #改
        # 灰階化
        gray_image = cv2.cvtColor(images, cv2.COLOR_BGR2GRAY)
        # 模糊處理
        blurred_image = cv2.GaussianBlur(gray_image, (5, 5), 1)
        # 自適應閾值
        binary_image = cv2.adaptiveThreshold(blurred_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 13, 3)
        # 侵蝕操作
        kernel = np.ones((3, 3), np.uint8)
        erosion = cv2.erode(binary_image, kernel, iterations=1)
        # 水平投影
        horizontal_projection = np.sum(erosion, axis=1)
        # 區域記錄
        is_in_block = False
        start_row = 0
        regions = []
        max_region = None
        max_region_sum = 0
        max_number=0
        # 掃描水平方向的投影，找出區域
        for row_index, pixel_sum in enumerate(horizontal_projection):
            if pixel_sum > 0:
                if not is_in_block:
                    start_row = row_index
                    is_in_block = True
            else:
                if is_in_block:
                    end_row = row_index
                    regions.append((start_row, end_row))  # 記錄區域
                    # 計算區域內白色像素和
                    region_sum = np.sum(horizontal_projection[start_row:end_row])
                    if region_sum > max_region_sum:
                        max_region_sum = region_sum
                        max_region = (start_row, end_row)
                    is_in_block = False

        # 找出最大區域及其前 5 個高度在 10 到 113 之間的區域
        max_region_index = regions.index(max_region) if max_region else -1
        highlight_regions = []
        if max_region:
            count = 0
            for i in range(max_region_index - 1, -1, -1):  # **從最大區域的上方開始搜尋**
                region = regions[i]
                if 20 <= (region[1] - region[0]):  # 避免畫出太小的區域
                    highlight_regions.append(region)
                    count += 1
                if count == 5:  # **只畫出前 5 個區域**
                    break

        #大改
        if step==1:
            step+=1
            highlight_regions.sort(key=lambda x: x[0])
            first_region = highlight_regions[0] if highlight_regions else None
            other_regions = highlight_regions[1:4] if len(highlight_regions) > 1 else []
            output_file = r'C:\seniorProject\LaiCode\two_bill\ele_output\out.txt'
            if first_region:
                num_to_english = {  10: "A", 11: "B", 12: "C", 13: "D", 14: "E", 15: "F", 16: "G", 17: "H", 18: "I", 19: "J",
                                    20: "K", 21: "L", 22: "M", 23: "N", 24: "O", 25: "P", 26: "Q", 27: "R", 28: "S", 29: "T",
                                    30: "U", 31: "V", 32: "W", 33: "X", 34: "Y", 35: "Z"}
                start, end = first_region
                cropped_region = images[start:end, :]  # 裁剪第一區域
                det_img, detections = Detect_1.image_detection( cropped_region, Detect_1.network, Detect_1.class_names, Detect_1.class_colors)
                boxes = []
                confidences = []
                class_ids = []

                for detection in detections:
                    label, confidence, bbox = detection
                    x, y, w, h = bbox
                    boxes.append([int(x - w // 2), int(y - h // 2), int(w), int(h)])  # YOLO 的框是以中心點計算的
                    confidences.append(float(confidence))
                    class_ids.append(int(label))

                # 設定 NMS 閾值
                nms_threshold = 0.4

                # 使用 OpenCV 的非極大值抑制
                indices = cv2.dnn.NMSBoxes(boxes, confidences, score_threshold=0.5, nms_threshold=nms_threshold)

                # 篩選出經過 NMS 處理的檢測結果
                filtered_detections = []
                if len(indices) > 0:
                    for i in indices.flatten():
                        filtered_detections.append((class_ids[i], confidences[i], boxes[i]))
                filtered_detections = [d for d in detections if float(d[1]) >= 50.0]
                sorted_detections = sorted(filtered_detections, key=lambda det: det[2][0])
                total_labels = len(sorted_detections)
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"字軌號碼：")
                    for det in sorted_detections:
                        label = det[0]  # 檢測的標籤名稱
                        # 如果標籤是數字且大於 9，轉換為英文
                        if label.isdigit() and int(label) > 9:
                            label = num_to_english.get(int(label), label)
                        f.write(f"{label}")  # 寫入標籤
                        global word_track
                        word_track += "".join(label)

                    # 如果標籤總數不足 10，附加 "*"
                    if total_labels < 10:
                        f.write("*")
                    f.write(f"\n")

        # 顯示其他區域
            for index, (start, end) in enumerate(other_regions):
                cropped_region = images[start:end, :]  # 裁剪其他區域
                det_img, detections = ele_Detect.image_detection(cropped_region, ele_Detect.network, ele_Detect.class_names, ele_Detect.class_colors)
                sorted_detections = sorted(detections, key=lambda det: det[2][0])
                filtered_detections = [d for d in sorted_detections if float(d[1]) >= 50.0]
                detected_numbers = [detection[0] for detection in sorted_detections]
                if index == 0:
                    first_eight_numbers = detected_numbers[:8]
                    with open(output_file, 'a', encoding='utf-8') as f:
                        f.write(f"日期：")
                        f.write("".join(first_eight_numbers)+"\n")

                        global date
                        date = "".join(first_eight_numbers)

                        if len(date) >= 4:
                            date_suffix = date[4:]  # 取出第 5 個字以後的內容
                            date_prefix = date[:4]  # 保存前 4 個字 EX:2024

                            TWdate = int(date_prefix) - 1911  # 轉換為整數後減 1911
                            date = str(TWdate) + date_suffix  # 轉回字串，拼接日期後半段


                if index == 1:
                    image_width = cropped_region.shape[1]
                    right_half_threshold = image_width // 2
                    right_half_numbers = [detection[0] for detection in sorted_detections if detection[2][0] > right_half_threshold]
                    with open(output_file, 'a', encoding='utf-8') as f:
                        number_str = ''.join(str(num) for row in right_half_numbers for num in row)
                        if number_str:  # 如果不為空
                            number = int(number_str)
                            max_number=number
                            result = math.ceil(number * 0.95)  # 無條件進位，計算銷售額
                            f.write(f"銷售額：{result}\n")
                            f.write(f"總計額：{number}\n")
                            total_amount = number
                            tax_free = number

                        else:  # 如果為空，處理默認情況
                            f.write("銷售額：0\n")
                            f.write("總計額：0\n")
                if index == 2:
                    global seller_number
                    with open(output_file, 'a', encoding='utf-8') as f:
                        if len(seller_number) < 8:
                            f.write(f"賣方統一編號：")
                            f.write("".join(detected_numbers) + "\n")
                            seller_number = "".join(detected_numbers)
                        else:
                            f.write(f"賣方統一編號：")
                            f.write("".join(detected_numbers[:8]) + "\n")
                            f.write(f"買方統一編號：")
                            f.write("".join(detected_numbers[8:]) + "\n")
                            seller_number = "".join(detected_numbers[:8])
#改
        if height > 2000 and max_region and step==2:
            print("正在執行step:",step)
            im=images.copy()
            red_box_regions = []
            grouped_numbers = []
            for start_row, end_row in regions:
                region_height = end_row - start_row
                if start_row > max_region[1]and 20 <= region_height:  # 確保區域在最大區域以下
                    red_box_regions.append((start_row, end_row))
                    cv2.rectangle(im, (0, start_row), ( im.shape[1], end_row), (0, 0, 255),2)  # 紅框
            if red_box_regions:
                for i, (start_row, end_row) in enumerate(red_box_regions):
                    cropped_region = images[start_row:end_row, :]
                    save_dir=r"C:\seniorProject\LaiCode\two_bill\ele_output"
                    base_name = os.path.splitext(os.path.basename(image_file))[0]
                    # output_gray = os.path.join(save_dir, f"{base_name}_{i}_drawn_image.png")
                    # cv2.imwrite(output_gray, cropped_region)
                    ic=cropped_region.copy()
                    gray_1= cv2.cvtColor(ic, cv2.COLOR_BGR2GRAY)
                    binary_1 = cv2.adaptiveThreshold(gray_1, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 13, 4)
                    # 建立 3x3 的矩形結構元素，用於形態學處理
                    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 2))
                    # 進行膨脹操作，使白色區域擴張，增強邊緣
                    binary = cv2.dilate(binary_1, kernel)
                    # 計算垂直投影
                    projection = np.sum(255 - binary, axis=0)  # 計算每列的黑色像素總數
                    # 找到間隔大的地方（分界點）
                    split_points = find_segment_intervals_with_visualization(projection, cropped_region,image_file)
                    for j, (start_x, end_x, _) in enumerate(split_points):
                        detected_numbers = []
                        # **步驟 1: 每次都產生新的 masked_image**
                        cas_image= cropped_region.copy()
                        cas_image= np.ones_like(cropped_region, dtype=np.uint8) * 255  # 先建立全白影像
                        # **步驟 2: 只保留當前區塊**
                        cas_image[:, start_x:end_x] = cropped_region[:, start_x:end_x]  # 先還原當前區塊
                        save_dir=r"C:\seniorProject\LaiCode\two_bill\ele_output"
                        base_name = os.path.splitext(os.path.basename(image_file))[0]
                        # output_gray = os.path.join(save_dir, f"{base_name}_{j}_image.png")
                        # cv2.imwrite(output_gray, cas_image)
                        """cv2.imshow(f"Region {j}", cas_image)
                        cv2.waitKey(0)  # 等待按鍵輸入
                        cv2.destroyAllWindows()"""

                        # **步驟 2: 送入 YOLO 進行物件偵測**
                        det_img, detections = ele_Detect.image_detection(cas_image, ele_Detect.network, ele_Detect.class_names, ele_Detect.class_colors)
                        final_number = ""  # **確保變數在單張圖片範圍內初始化**
                        # **步驟 3: 提取偵測到的數字，並存入 (x, number) 格式**
                        detected_data = []  # 存放 (X 軸位置, 數字)
                        for detection in detections:
                            class_id = int(detection[0])  # 確保是整數索引
                            x_pos = int(detection[2][0])  # 提取 `bounding box` 的中心 X 座標
                            if 0 <= class_id < len(ele_Detect.class_names):  # 確保索引不超出範圍
                                detected_data.append((x_pos, ele_Detect.class_names[class_id]))  # 存入 (X, 數字)
                        # **步驟 4: 按 X 軸排序**
                        detected_data.sort(key=lambda x: x[0])  # 依照 X 軸位置排序
                        # **步驟 5: 提取排序後的數字**
                        detected_numbers = [num for _, num in detected_data]
                        # **步驟 6: 決定是否加入 `0` 或跳過**
                        if detected_numbers:
                            final_number = "".join(detected_numbers)  # 只有在有數字時才合併
                            grouped_numbers.append(int(final_number))  # 存入合併後的整數
                        # **步驟 7: 顯示 YOLO 偵測結果**
                        """print(f"當前區塊 {i}-{j} 排序後的數字: {detected_numbers}")
                        print(f"更新後的 grouped_numbers: {grouped_numbers}")
                        cv2.imshow(f"YOLO Detection {i}-{j}", det_img)
                        cv2.waitKey(0)
                        cv2.destroyAllWindows()"""
                tax=int(total_amount*0.05)
                dtax_matrix = [num for num in grouped_numbers if tax< num < total_amount]
                tax_matrix =[num for num in grouped_numbers if 0< num <= (tax+1)]
                print(dtax_matrix)
                print(tax_matrix)
                found_pairs = []
                for num1 in dtax_matrix:
                    for num2 in tax_matrix:
                        if num1 + num2 == total_amount:
                            found_pairs.append((num1, num2))
                # **輸出結果**
                if found_pairs:
                    first_pair = found_pairs[0]
                    tax_price = max(first_pair)  # 應稅銷售額
                    non_tax_price = min(first_pair)  # 稅額

                    rate = non_tax_price
                    tax_amount = tax_price
                    tax_free = 0
                    print(f"稅額: {non_tax_price}, 免稅額: {tax_price}")
                    # with open(output_file, 'a', encoding='utf-8') as f:
                    #             f.write(f"稅額：{non_tax_price}\n")
                    #             f.write(f"免稅額：{tax_price}\n")
                """resized_projection = resize_image_for_display(im)
                cv2.imshow("warimage", resized_projection)
                cv2.waitKey(0)
                cv2.destroyAllWindows()"""
            # else:
            #     with open(output_file, 'a', encoding='utf-8') as f:
            #                     f.write(f"稅額：0\n")
            #                     f.write(f"免稅額：0\n")

        # with open(output_file, 'a', encoding='utf-8') as f:
        #     f.write("-" * 50 + "\n")
    #改
    def find_segment_intervals_with_visualization(projection, image,image_file):
        """
        在灰階圖片上以矩形框顯示垂直投影結果（不轉彩色）
        - image: 二值化影像（黑色前景，白色背景）
        """
        height = image.shape[0]

        # **步驟 1: 合併連續黑色像素區域**
        segments = []
        start_x = None

        for x in range(len(projection)):
            if projection[x] > 1:  # 只考慮黑色像素較多的區域
                if start_x is None:
                    start_x = x  # 記錄起點
                end_x = x  # 記錄終點
            else:
                if start_x is not None:
                    if end_x - start_x > 1:  # 過濾掉太小的區域
                        max_height = max(projection[start_x:end_x])
                        segments.append((start_x, end_x, max_height))  # 記錄框的位置
                    start_x = None  # 重置區間

        # **步驟 2: 合併相近的框**
        merged_segments = []
        prev_start, prev_end, prev_height = segments[0] if segments else (None, None, None)

        for i in range(1, len(segments)):
            start, end, max_height = segments[i]

            if start - prev_end <= 20:  # 如果兩個框的距離小於 merge_threshold，則合併
                prev_end = end  # 擴展框的範圍
                prev_height = max(prev_height, max_height)  # 框的高度取最大值
            else:
                #改
                merged_segments.append((prev_start-10, prev_end+15, prev_height))
                prev_start, prev_end, prev_height = start, end, max_height

        # 添加最後一個框
        if prev_start is not None:
            #改
            merged_segments.append((prev_start-10, prev_end+15, prev_height))

        """# **步驟 3: 在圖像上畫框**
        output_image = image.copy()
        for start, end, max_height in merged_segments:
            cv2.rectangle(output_image, (start, height - max_height), (end, height), 255, 1)

        # 顯示影像
        cv2.imshow("Merged Vertical Projection", output_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()"""
        return  merged_segments


    success_log_file = r'C:\seniorProject\LaiCode\two_bill\ele_output\out.txt'

    image = cv2.imread(image_path)

    with open(success_log_file, 'a', encoding='utf-8') as f:
                f.write(f"檔案名稱：{image_name}\n")

    process_left_half(colorful_edge(image), image_name,image)

###########################################################################################################


def traditional_invoice(image_path, image_name):

    # 定義圖片所在的資料夾路徑
    folder_path = r"C:\seniorProject\LaiCode\two_bill\img"
    date_output_folder_path = r"C:\seniorProject\LaiCode\two_bill\output\date"
    number_output_folder_path = r"C:\seniorProject\LaiCode\two_bill\output\number"
    mid_output_folder_path = r"C:\seniorProject\LaiCode\two_bill\output\mid"

    # 如果不存在，創建輸出資料夾
    if not os.path.exists(date_output_folder_path):
        os.makedirs(date_output_folder_path)
    if not os.path.exists(number_output_folder_path):
        os.makedirs(number_output_folder_path)
    # if not os.path.exists(mid_output_folder_path):
    #     os.makedirs(mid_output_folder_path)

    def start(image_path,image_name):

        # 打開圖片
        image = Image.open(image_path)
        filename = image_name
        # 圖片大小
        #global width, height
        width, height = image.size

        ################### 邊邊角角最容易錯 而且又沒有我要的東西 所以我都多切一點 ###################

        # 定義日期區域 (0~5%)，日期位於圖片最上方的區域
        date_area = (width * 0.05, height * 0.01, width * 0.98, height * 0.09)
        global dateTemp #記高度 我要框起來
        dateTemp = int(abs(height * 0.01))  # 確保 dateTemp 是正整數

        # 定義發票號碼區域 (10~15%)，號碼大約位於圖片的指定區域
        number_area = (0, height * 0.1, width * 0.9, height * 0.2025)
        global numberTemp #記高度 我要框起來
        numberTemp = int(abs(height * 0.1))  # 確保 dateTemp 是正整數

        #number_area2 = (width * 0.02, height * 0.1, width * 0.17, height * 0.2025)

        # # 定義中間明細區域
        # mid_area = (width * 0.01, height * 0.22, width * 0.98, height * 0.75)

        # 裁剪日期
        date_img = image.crop(date_area)
        date_output_path = os.path.join(date_output_folder_path, f"{os.path.splitext(filename)[0]}_date.jpg")
        date_img.save(date_output_path)
        # 將新的文件名（a1_date.jpg）保存到 filename 變數
        datefilename = os.path.basename(date_output_path)  # 只取文件名部分

        date(date_output_path,r"C:\seniorProject\LaiCode\two_bill\output\date\OK",datefilename)

        ################################################################################################################

        # 裁剪發票號碼
        number_img = image.crop(number_area)
        number_output_path = os.path.join(number_output_folder_path, f"{os.path.splitext(filename)[0]}-1_number.jpg")
        number_img.save(number_output_path)
        # 將新的文件名（a1_date.jpg）保存到 filename 變數
        numberfilename = os.path.basename(number_output_path)  # 只取文件名部分

        number(number_output_path,r"C:\seniorProject\LaiCode\two_bill\output\number\OK",numberfilename)

        ################################################################################################################

        # number_img = image.crop(number_area2)
        # number_output_path = os.path.join(number_output_folder_path, f"{os.path.splitext(filename)[0]}-2_number.jpg")
        # number_img.save(number_output_path)
        # # 將新的文件名（a1_date.jpg）保存到 filename 變數
        # numberfilename = os.path.basename(number_output_path)  # 只取文件名部分

        # number(number_output_path,r"C:\seniorProject\LaiCode\main\output_img\number\OK",numberfilename)

        ################################################################################################################

        # # 裁剪日期
        # mid_img = img.crop(mid_area)
        # mid_output_path = os.path.join(mid_output_folder_path, f"{os.path.splitext(filename)[0]}_mid.jpg")
        # mid_img.save(mid_output_path)

        #print(f"Processed {filename}")

    #print("處理完日期跟號碼")

    def date(file_path, save_folder, datefilename):

        image1 = cv2.imread(file_path)

        # 将图像转换为灰度图
        gray = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)

        # 使用大津法进行二值化 是自適應的一種 大津法：全局阈值化，适用于光照均匀的图像。自适应阈值：局部阈值化，适用于光照不均匀的图像。
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 将检测到的文本部分变为黑色，其余变为白色
        #result = np.where(binary == 0, 0, 255).astype(np.uint8)  # 转换为uint8类型

        # 水平投影
        (h1, w1) = binary.shape  # 获取图像的高和宽
        a = [0 for _ in range(0, h1)]  # 初始化一个长度为h的数组，用于记录每一行的黑点个数

        # 记录每一行的黑点个数
        for j in range(0, h1):
            for i in range(0, w1):
                if binary[j, i] == 0:
                    a[j] += 1

        # for j in range(0, h1):
        #     for i in range(0, a[j]):
        #         binary[j, i] = 0

        # # 显示水平投影结果
        # plt.imshow(binary, cmap="gray")  # 灰度图正确的表示方法
        # plt.show()

        # 定义黑色像素阈值，只有黑色像素量超过这个值，才会被认为是有文字的行
        threshold = 100  # 可根据具体情况调整该值

        # 找到第一个有足够黑色像素的行以及结束的行
        first_black_row = 0
        end = 0
        found_first = False

        for j in range(h1):
            if a[j] > threshold and not found_first:
                first_black_row = j
                found_first = True
            if found_first and a[j] <= threshold:
                end = j
                break

        # 如果没有找到结束行，默认到图像底部
        if end == 0:
            end = h1

        # 检查 first_black_row 和 end 是否有效
        if first_black_row >= end or first_black_row < 0 or end > h1:
            print(f"裁剪范围无效，对文件: {datefilename}")
            return 0

        #print(f"有效文字区域的Y轴位置: {first_black_row} ~ {end} 对文件: {datefilename}")

        # 裁剪图像：保留从第一个黑色区域到找到的结束行之间的部分，确保裁剪区域不超出边界
        top = max(0, first_black_row - 10)
        bottom = min(h1, end + 10)
        cropped_image = image1[top:bottom, :]

        # 确保裁剪后的图像非空
        if cropped_image.size == 0:
            print(f"裁剪后的图像为空，对文件: {datefilename}")
            return 0

        # 生成保存的文件路径，基于原文件名避免覆盖
        save_path = os.path.join(save_folder, f"cropped_{datefilename}")

        # 保存裁剪后的图片
        cv2.imwrite(save_path, cropped_image)


        ###################################################### 這裡以下的是 把字去掉 "中華民國 xxx 年 x-x 月分"

        # 讀取圖像
        img = cv2.imread(save_path)

        # 計算圖像的寬度
        height1, width1, _ = img.shape
        left = int(0.14 * width1)   # 計算左側 15% 的邊界
        right = int(0.99 * width1)  # 計算右側 99% 的邊界

        # 將左側 15% 設為白色
        img[:, :left] = 255

        # 將右側 5% 設為白色
        img[:, right:] = 255

        # 將新的文件名（a1_date.jpg）保存到 filename 變數
        #filename = os.path.basename(file_path)  # 只取文件名部分

        # 将图像转换为灰度图
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 使用高斯模糊来平滑图像，减少噪声
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)

        # 使用大津法进行二值化 是自適應的一種 大津法：全局阈值化，适用于光照均匀的图像。自适应阈值：局部阈值化，适用于光照不均匀的图像。
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 将检测到的文本部分变为黑色，其余变为白色
        result = np.where(binary == 0, 0, 255).astype(np.uint8)  # 转换为uint8类型


        # 获取图像的高和宽度
        (h2, w2) = binary.shape

        # # 计算保留的宽度部分
        # left = int(0)  # 0% 的宽度
        # right = int(w2)  # 100% 的宽度

        # # 裁剪图像的中间宽度部分
        # result_cropped = result[:, left:right]

        # 垂直投影
        b = [0 for z in range(0, w2)]  #b = [0,0,0,0,0,0,0,0,0,0,...,0,0]初始化一个长度为w的数组，用于记录每一列的黑点个数

        #记录每一列的波峰
        for j in range(0,w2): #遍历一列
            for i in range(0,h2):  #遍历一行
                if  binary[i,j]==0:  #如果该点为黑点
                    b[j]+=1  #该列的计数器加一，最后统计出每一列的黑点个数
                    binary[i,j]=255  #记录完后将其变为白色 ，相当于擦去原图黑色部分

        for j  in range(0,w2):
            for i in range((h2-b[j]),h2):  #从该列应该变黑的最顶部的点开始向最底部涂黑
                binary[i,j]=0   #涂黑

        # # 显示水平投影结果
        # plt.imshow(binary, cmap="gray")  # 灰度图正确的表示方法
        # plt.show()

        # # # 顯示處理後的圖像
        # cv2.imshow("Processed Image", result)
        # cv2.waitKey(0)  # 按任意鍵關閉視窗
        # cv2.destroyAllWindows()

        # 初始化變數
        char_count = 0  # 字符計數
        threshold = 5  # 判定字符區域的像素閾值
        start_col = None  # 當前字符的起始列
        fourth_char_end = None  # 第四個字符的結尾位置
        eighth_char_start = None  # 第八個字符的起始列
        eighth_char_end = None  # 第八個字符的結尾列
        last_two_end = None  # 倒數第二個字符的結尾列
        last_two_start = None  # 倒數第二個字符的起始列

        # 正向遍歷，找到前8字的相關位置
        for j in range(w2):
            if b[j] > threshold:  # 發現有黑色像素的列
                if start_col is None:  # 表示找到一個新字符的開始
                    start_col = j
            else:
                if start_col is not None:  # 表示字符結束
                    char_count += 1  # 字符數量加1

                    # 記錄第四個字的結尾
                    if char_count == 4:
                        fourth_char_end = j - 1  # 記錄第4個字符的結尾列

                    # 記錄第八個字的開頭和結尾
                    if char_count == 8:
                        eighth_char_start = start_col  # 記錄第8個字符的起始列
                        eighth_char_end = j - 1  # 記錄第8個字符的結尾列

                    start_col = None  # 重置字符起始列

        # 反向遍歷，從右到左找到倒數第1和第2字的位置
        char_count = 0  # 重置字符計數
        temp = 0
        for j in range(w2 - 1, -1, -1):  # 從右向左掃描
            if b[j] > threshold + 5:  # 發現有黑色像素的列
                if start_col is None:  # 表示找到一個新字符的開始
                    start_col = j
            else:
                if start_col is not None:  # 表示字符結束
                    char_count += 1  # 字符數量加1
                    temp = j
                    # 記錄倒數第一個和第二個字符的範圍
                    if char_count == 1:
                        last_two_end = start_col  # 倒數第一個字的結尾
                    elif char_count == 2:
                        last_two_start = start_col  # 倒數第二個字的起始列
                        break  # 已找到倒數兩字，結束搜尋

                    start_col = None  # 重置字符起始列

        # 1. 將第五個字以前的部分覆蓋為白色
        if fourth_char_end is not None:
            result[:, :fourth_char_end + 1] = 255  # 包括第4字結尾

        # 2. 將第八個字覆蓋為白色
        if eighth_char_start is not None and eighth_char_end is not None:
            result[:, eighth_char_start:eighth_char_end + 1] = 255  # 第8字範圍

        # 3. 從倒數第二個字到結尾覆蓋為白色
        if temp is not None:
            result[:, temp:] = 255  # 倒數兩個字及以後範圍

        output_path = os.path.join(r"C:\seniorProject\LaiCode\two_bill\output\date\OK\OK2", datefilename)

        # 保存處理後的圖像
        cv2.imwrite(output_path, result)
        #print(f"處理後的圖像已保存到：{output_path}")

        # 顯示處理後的圖像
        # cv2.imshow("Processed Image", img)
        # cv2.waitKey(0)  # 按任意鍵關閉視窗
        # cv2.destroyAllWindows()

        global date
        date = RecognitionNumber(output_path,"date") #辨識
        
        if '7' in date[:2]:
            date = date.replace('7', '1')
            
        # 檢查 date 是否至少有 4 個字，並取出第 4 個字以後的內容
        if len(date) >= 4 and (date[:2] == "10" or date[:2] == "11" or date[:1] == "9"): #年份一定是90,100,110年代
            date_suffix = date[3:]  # 取出第 4 個字以後的內容
            date_prefix = date[:3]  # 保存前 3 個字 EX:113
            if any(char in date_suffix for char in ["1", "2"]) and len(date_suffix) <= 2:
                date = date_prefix + "0102"
            elif any(char in date_suffix for char in ["3", "4"]):
                date = date_prefix + "0304"
            elif any(char in date_suffix for char in ["5", "6"]):
                date = date_prefix + "0506"
            elif any(char in date_suffix for char in ["7", "8"]):
                date = date_prefix + "0708"
            elif any(char in date_suffix for char in ["9", "0"]):
                date = date_prefix + "0910"
            elif any(char in date_suffix for char in ["1", "2"]) and len(date_suffix) >= 3:
                date = date_prefix + "1112"
        
        if len(date) != 7:
            # 初始化變數
            char_count = 0  # 字符計數
            threshold = 9  # 判定字符區域的像素閾值
            start_col = None  # 當前字符的起始列
            fourth_char_end = None  # 第四個字符的結尾位置
            eighth_char_start = None  # 第八個字符的起始列
            eighth_char_end = None  # 第八個字符的結尾列
            last_two_end = None  # 倒數第二個字符的結尾列
            last_two_start = None  # 倒數第二個字符的起始列
            #a = 0
            # 正向遍歷，找到前8字的相關位置
            for j in range(w2):
                if b[j] > threshold:  # 發現有黑色像素的列

                    if start_col is None:  # 表示找到一個新字符的開始
                        start_col = j
                else:
                    if start_col is not None:  # 表示字符結束
                        char_count += 1  # 字符數量加1

                        # 記錄第四個字的結尾
                        if char_count == 4:
                            fourth_char_end = j - 1  # 記錄第4個字符的結尾列

                        # 記錄第八個字的開頭和結尾
                        if char_count == 8:
                            eighth_char_start = start_col  # 記錄第8個字符的起始列
                            eighth_char_end = j - 1  # 記錄第8個字符的結尾列

                        start_col = None  # 重置字符起始列

            # 反向遍歷，從右到左找到倒數第1和第2字的位置
            char_count = 0  # 重置字符計數
            temp = 0
            for j in range(w2 - 1, -1, -1):  # 從右向左掃描
                if b[j] > threshold + 5:  # 發現有黑色像素的列
                    if start_col is None:  # 表示找到一個新字符的開始
                        start_col = j
                else:
                    if start_col is not None:  # 表示字符結束
                        char_count += 1  # 字符數量加1
                        temp = j
                        # 記錄倒數第一個和第二個字符的範圍
                        if char_count == 1:
                            last_two_end = start_col  # 倒數第一個字的結尾
                        elif char_count == 2:
                            last_two_start = start_col  # 倒數第二個字的起始列
                            break  # 已找到倒數兩字，結束搜尋

                        start_col = None  # 重置字符起始列

            # 1. 將第五個字以前的部分覆蓋為白色
            if fourth_char_end is not None:
                result[:, :fourth_char_end + 1] = 255  # 包括第4字結尾

            # 2. 將第八個字覆蓋為白色
            if eighth_char_start is not None and eighth_char_end is not None:
                result[:, eighth_char_start:eighth_char_end + 1] = 255  # 第8字範圍

            # 3. 從倒數第二個字到結尾覆蓋為白色
            if temp is not None:
                result[:, temp:] = 255  # 倒數兩個字及以後範圍

            output_path = os.path.join(r"C:\seniorProject\LaiCode\two_bill\output\date\OK\OK2\OK3", datefilename)

            # 保存處理後的圖像
            cv2.imwrite(output_path, result)
            #print(f"處理後的圖像已保存到：{output_path}")

            # 顯示處理後的圖像
            # cv2.imshow("Processed Image", img)
            # cv2.waitKey(0)  # 按任意鍵關閉視窗
            # cv2.destroyAllWindows()
            
            date = RecognitionNumber(output_path,"date") #辨識
            
            if '7' in date[:2]:
                date = date.replace('7', '1')
            
            # 檢查 date 是否至少有 4 個字，並取出第 4 個字以後的內容
            if len(date) >= 4 and (date[:2] == "10" or date[:2] == "11" or date[:1] == "9"): #年份一定是90,100,110年代
                date_suffix = date[3:]  # 取出第 4 個字以後的內容
                date_prefix = date[:3]  # 保存前 3 個字 EX:113
                if any(char in date_suffix for char in ["1", "2"]) and len(date_suffix) <= 2:
                    date = date_prefix + "0102"
                elif any(char in date_suffix for char in ["3", "4"]):
                    date = date_prefix + "0304"
                elif any(char in date_suffix for char in ["5", "6"]):
                    date = date_prefix + "0506"
                elif any(char in date_suffix for char in ["7", "8"]):
                    date = date_prefix + "0708"
                elif any(char in date_suffix for char in ["9", "0"]):
                    date = date_prefix + "0910"
                elif any(char in date_suffix for char in ["1", "2"]) and len(date_suffix) >= 3:
                    date = date_prefix + "1112"
        

        #EN_NUM(output_path, 1)

        #print(f"已保存裁剪后的图片到: {save_path}")

        ############################## 這裡是要畫框框的 ##############################
        # 在圖片上繪製矩形，顏色為紅色，線條粗細為2
        #global width
        cv2.rectangle(finalImage, ( 0, dateTemp + top), (width, dateTemp + bottom), (0, 255, 255), 2)

        #print("所有日期處理完成！")


    def number(file_path, save_folder,numberfilename):

        image1 = cv2.imread(file_path)

        # 将图像转换为灰度图
        gray = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)

        # 使用高斯模糊来平滑图像，减少噪声
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)

        binary = cv2.adaptiveThreshold(blurred, 255,
                                                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                cv2.THRESH_BINARY, 13, 4)

        # 将检测到的文本部分变为黑色，其余变为白色
        result = np.where(binary == 0, 0, 255).astype(np.uint8)  # 转换为uint8类型

        # plt.imshow(binary, cmap="gray")  # 灰度图正确的表示方法
        # plt.show()

        # 获取图像的高和宽度
        (h2, w2) = binary.shape

        # 计算保留的宽度部分
        left = int(0)  # 0% 的宽度
        right = int(w2)  # 100% 的宽度

        # 裁剪图像的中间宽度部分
        result_cropped = result[:, left:right]

        # 垂直投影
        b = [0 for z in range(0, w2)]  #b = [0,0,0,0,0,0,0,0,0,0,...,0,0]初始化一个长度为w的数组，用于记录每一列的黑点个数

        #记录每一列的波峰
        for j in range(0,w2): #遍历一列
            for i in range(0,h2):  #遍历一行
                if  binary[i,j]==0:  #如果该点为黑点
                    b[j]+=1  #该列的计数器加一，最后统计出每一列的黑点个数
                    binary[i,j]=255  #记录完后将其变为白色 ，相当于擦去原图黑色部分

        # for j  in range(0,w2):
        #     for i in range((h2-b[j]),h2):  #从该列应该变黑的最顶部的点开始向最底部涂黑
        #         binary[i,j]=0   #涂黑

        # # 显示投影结果
        # plt.imshow(binary, cmap="gray")  # 灰度图正确的表示方法
        # plt.show()

        # 找出最宽的黑色区域
        max_width = 0  # 最宽区域的宽度
        current_width = 0  # 当前连续黑色区域的宽度
        start_col = 0  # 当前区域的开始列
        best_start_col = 0  # 记录最宽区域的开始列
        best_end_col = 0  # 记录最宽区域的结束列
        rightmost_col = 0  # 把邊邊掃描沒掃好的地方記錄下來 等等要去除掉

        # 设置一个阈值，用于确定有效的区域
        threshold = 10  # 这个值可以根据实际情况调整

        for j in range(0, w2):
            if b[j] > threshold:  # 发现有黑色像素的列
                if current_width == 0:  # 开始新的黑色区域
                    start_col = j
                current_width += 1  # 增加当前区域的宽度

                # 看他是不是旁邊的 掃描掃不好的東西 黑黑一條
                if b[j] > 300:
                    rightmost_col = j + 3  # +3是因為把她除乾淨

            else:
                if current_width > max_width:  # 当前区域宽度超过阈值且比记录的最宽区域宽
                    max_width = current_width
                    best_start_col = start_col
                    best_end_col = j - 1  # 结束列是当前列的前一列
                current_width = 0  # 重置当前区域的宽度

        # 检查最后一个区域是否是最宽的，并且宽度要大于阈值
        if current_width > max_width:
            max_width = current_width
            best_start_col = start_col
            best_end_col = w2 - 1  # 如果最后一个区域是最宽的，结束列是最后一列

        # 输出结果
        # if max_width > threshold:
        #     print(f"最宽的黑色区域范围: 开始列 {best_start_col}, 结束列 {best_end_col}, 宽度 {max_width}")
        # else:
        #     print("没有找到超过阈值的黑色区域")

        # 获取切割的列位置
        left_image  = image1[ : ,  rightmost_col  : best_start_col  ]  # 左边部分，从0列到best_start_col列
        right_image = image1[ : ,  best_start_col :                 ]  # 右边部分，从best_start_col列到最后

        # 保存左右两张图片
        left_image_path = os.path.join(r"C:\seniorProject\LaiCode\two_bill\output\number", f"{os.path.splitext(image_name)[0]}_En.jpg")
        right_image_path = os.path.join(r"C:\seniorProject\LaiCode\two_bill\output\number", f"{os.path.splitext(image_name)[0]}_Num.jpg")

        cv2.imwrite(left_image_path, left_image) #存圖片
        cv2.imwrite(right_image_path, right_image)

        #print(f"圖片成功保存：\n左圖：{left_image_path}\n右圖：{right_image_path}")

        #Recognition(left_image_path)  #辨識
        tempWidth = 0
        EN_NUM(left_image_path, tempWidth) #切仔細 (左右)


        # with open(r"C:\seniorProject\LaiCode\main\dataTemp\data.txt", "a", encoding="utf-8") as file: #先寫前面的字
        #     file.write("號碼：")
        # Recognition(right_image_path) #辨識

        tempWidth = best_start_col
        EN_NUM(right_image_path, tempWidth)

        ########################開始做侵蝕膨脹##########################
        # # 遍历文件夹中的所有图片

        # image1 = cv2.imread(save_path)

        # img = cv2.imread(save_path)
        # #cv2.imshow("oxxostudio1", img)   # 原始影像

        # #img2 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

        # #################我是白底黑字 所以我把兩個順序反過來###################
        # img = cv2.dilate(img, kernel)    # 膨脹，白色小點消失
        # #cv2.imshow("oxxostudio3", img)   # 膨脹後的影像

        # img = cv2.erode(img, kernel)     # 侵蝕，將白色小圓點移除
        # #cv2.imshow("oxxostudio2", img)   # 侵蝕後的影像

        # #cv2.waitKey(0)                   # 按下 q 鍵停止
        # #cv2.destroyAllWindows()

        # # 生成保存的文件路径，基于原文件名避免覆盖
        # save_path = os.path.join(r"C:\seniorProject\LaiCode\main\output_img\number\OK\ErosionDilation", f"final_{numberfilename}")

        # # 保存裁剪后的图片
        # cv2.imwrite(save_path, img)

        #print("所有號碼處理完成！")

    def EN_NUM(file_path, tempWidth):

        image1 = cv2.imread(file_path)

        # 將新的文件名（a1_date.jpg）保存到 filename 變數
        filename = os.path.basename(file_path)  # 只取文件名部分

        # 將圖像轉換為灰度圖
        gray = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
        #cv2.imshow("Grayscale Image", gray)  # 顯示灰階圖

        # 使用高斯模糊來平滑圖像，減少噪聲
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        #cv2.imshow("Blurred Image", blurred)  # 顯示模糊後的圖

        # 使用大津法進行二值化 #改0409
        if tempWidth == 0: # tempWidth = 0 是英文
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            #cv2.imshow("Binary Image (Otsu's Threshold)", binary)  # 顯示二值化結果
        else: # tempWidth = 1 是數字
            #test~0409
            otsu_thresh, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            print(f"Otsu 原始閾值: {otsu_thresh}")

            # 提高閾值，例如提高 10（根據實驗可調）
            adjusted_thresh = otsu_thresh - 40  
            adjusted_thresh = max(0, min(adjusted_thresh, 255))  # 確保值在 0~255 之間
            
            _, binary = cv2.threshold(blurred, adjusted_thresh, 255, cv2.THRESH_BINARY)

            # cv2.imshow("Binary Image", binary)
            # cv2.waitKey(0)
            # cv2.destroyAllWindows()

        # 將檢測到的文本部分變為黑色，其餘變為白色
        result = np.where(binary == 0, 0, 255).astype(np.uint8)  # 轉換為 uint8 類型
        #cv2.imshow("Final Processed Image", result)  # 顯示最終結果

        # 等待按鍵後關閉所有窗口
        #cv2.waitKey(0)
        #cv2.destroyAllWindows()

        # 获取图像的高和宽度
        (h1, w1) = binary.shape

        # 计算保留的宽度部分
        left = int(0)  # 0% 的宽度
        right = int(w1)  # 100% 的宽度

        # 裁剪图像的中间宽度部分
        result_cropped = result[:, left:right]

        # 水平投影
        a = [0 for _ in range(0, h1)]  # 初始化一个长度为h的数组，用于记录每一行的黑点个数

        # 记录每一行的黑点个数
        for j in range(0, h1):
            for i in range(0, w1):
                if binary[j, i] == 0:
                    a[j] += 1

        # for j in range(0, h1):
        #     for i in range(0, a[j]):
        #         binary[j, i] = 0

        # # 显示水平投影结果
        # plt.imshow(binary, cmap="gray")  # 灰度图正确的表示方法
        # plt.show()

        # 设置一个阈值，用于确定有效的区域
        threshold = 10  # 这个值可以根据实际情况调整
        first_black_row = 0
        end = 0
        found_first = False
        # 找到第一个和最后一个大于阈值的行
        for j in range(h1):
            if a[j] > threshold and not found_first:
                first_black_row = j
                found_first = True
            if found_first and a[j] <= threshold:
                end = j
                break

        # 如果没有找到结束行，默认到图像底部
        if end == 0:
            end = h1

        # 检查 first_black_row 和 end 是否有效
        if first_black_row >= end or first_black_row < 0 or end > h1:
            print(f"裁剪范围无效，对文件: {filename}")
            return 0

        # 裁剪图像：保留从第一个黑色区域到找到的结束行之间的部分，确保裁剪区域不超出边界
        top = max(0, first_black_row - 3)
        bottom = min(h1, end + 3)
        cropped_image = result_cropped[top:bottom, :]

        # 检查 first_black_row 和 end 是否有效
        if first_black_row >= end or first_black_row < 0 or end > h1:
            print(f"裁剪范围无效，对文件: {filename}")
            return 0

        # 确保裁剪后的图像非空
        if cropped_image.size == 0:
            print(f"裁剪后的图像为空，对文件: {filename}")
            return 0

        # 将裁剪后的图像转换为 PIL 格式
        cropped_image_pil = Image.fromarray(cv2.cvtColor(cropped_image, cv2.COLOR_BGR2RGB))

        # 加長邊邊 因為我的圖片要長得像訓練權重時的圖 800*64 練的那些圖如果是888*88 我現在辨識的圖就要是 888*88 才不會失真
        if tempWidth == 0:
            left_padding = 150  # 左边增加的像素数
            right_padding = 600  # 右边增加的像素数
            top_padding = 0      # 上方增加的像素数
            bottom_padding = 0   # 下方增加的像素数
        # elif tempWidth == 1:
        #     left_padding = 200  # 左邊增加的像素數
        #     right_padding = 120  # 右邊增加的像素數
        #     top_padding = 0  # 上方增加的像素數
        #     bottom_padding = 0  # 下方增加的像素數
        else:
            left_padding = 280  # 左邊增加的像素數
            right_padding = 180  # 右邊增加的像素數
            top_padding = 0  # 上方增加的像素數
            bottom_padding = 0  # 下方增加的像素數

        # 计算新的画布尺寸
        original_width = cropped_image_pil.width
        original_height = cropped_image_pil.height
        new_width = original_width + left_padding + right_padding
        new_height = original_height + top_padding + bottom_padding

        # 创建新图片，背景颜色为白色
        new_img = Image.new("RGB", (new_width, new_height), color=(255, 255, 255))

        # 将裁剪后的图片贴到新画布
        new_img.paste(cropped_image_pil, (left_padding, top_padding))

        # 生成保存的文件路径，基于原文件名避免覆盖
        save_path = os.path.join(r"C:\seniorProject\LaiCode\two_bill\output\number\OK", f"OK_{filename}")

        # 保存最终的图片
        new_img.save(save_path)

        if tempWidth == 0 : #如果 tempWidth != 0 的話 他就不是英文 他是數字的部分
            with open(r"C:\seniorProject\LaiCode\two_bill\two_output\data\data.txt", "a", encoding="utf-8") as file: #先寫前面的字
                file.write("\n字軌號碼：")

        # if tempWidth == 1 : #如果 tempWidth != 0 的話 他就不是英文 他是數字的部分
        #     with open(r"C:\seniorProject\LaiCode\two_bill\two_output\data\data.txt", "a", encoding="utf-8") as file: #先寫前面的字
        #         file.write("\n月份：")

        global word_track
        if tempWidth == 0:
            tempword_track = RecognitionNumber(save_path,"EN") #辨識
        else:
            tempword_track = RecognitionNumber(save_path) #辨識
            
        word_track += tempword_track

        ############################## 這裡是要畫框框的 ##############################
        # 在圖片上繪製矩形，顏色為紅色，線條粗細為2
        cv2.rectangle(finalImage, (left + tempWidth, numberTemp + top), (right + tempWidth, numberTemp + bottom), (0, 128, 255), 2)

        #print(f"已保存裁剪后的图片到: {save_path}")

    #匹配統編跟電話
    #改 0409 本來是 threshold = 0.7
    def template_No_Tel(image_path, template_folder, threshold=0.65, nms_threshold=0.3, output_folder=r"C:\seniorProject\LaiCode\two_bill\output\template"):
        global seller_number
        global buyer_number
        # 讀取影像
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            print(f"無法讀取影像: {image_path}")
            return 0

                # 取得原圖的名稱，去掉副檔名
        original_name = os.path.splitext(image_name)[0]

        # 保存原始影像的副本用於截圖
        original_image = image.copy()

        highest_confidence = 0
        best_match = None
        best_rect = None


        # 儲存所有匹配結果
        match_results = []

        # 遍歷資料夾內的所有模板
        for template_name in os.listdir(template_folder):
            template_path = os.path.join(template_folder, template_name)

            # 確保只處理圖像文件
            if not template_name.lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            # 讀取模板圖像
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                print(f"無法讀取模板: {template_path}")
                continue

            # 進行模板匹配
            result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)

            # 找到符合閾值的匹配位置
            loc = np.where(result >= threshold)
            rects = []
            confidences = []

            for pt in zip(*loc[::-1]):
                x, y = pt
                confidence = result[y, x]
                rects.append([x, y, x + template.shape[1], y + template.shape[0]])
                confidences.append(float(confidence))

            # 使用非極大值抑制來去除重疊的框
            if len(rects) > 0:
                rects = np.array(rects)
                confidences = np.array(confidences)
                indices = cv2.dnn.NMSBoxes(rects.tolist(), confidences.tolist(), threshold, nms_threshold)

                # 儲存過濾後的匹配結果
                if len(indices) > 0:
                    for i in indices.flatten():
                        match_results.append((confidences[i], rects[i]))

        # 如果有匹配結果
        if match_results:
            # 根據信心度排序，取前 2 個
            top_matches = sorted(match_results, key=lambda x: x[0], reverse=True)[:2]

            # 如果只有一個匹配結果，直接當作「賣方」
            if len(top_matches) == 1:
                (conf, (x1, y1, x2, y2)) = top_matches[0]
                height, width = original_image.shape[:2]

                # 截取匹配到的整條
                seller_crop = original_image[y1 - 5 : y2 + 5, :]
                
                ############################# 把模板部分變白色 這樣就不會把o辨識成0 ##############################
                # 設定匹配到的區域為白色
                relative_y1 = 5  # 因為已經多裁切了 5 個像素
                relative_y2 = (y2 - y1) + 5
                seller_crop[relative_y1:relative_y2, x1:x2] = 255
                ######################################################################################
                
                # 繪製賣方框（黃色）
                cv2.rectangle(finalImage, (0, y1 - 5), (width, y2 + 5), (255, 0, 0), 2)

                # 保存影像（賣方）
                seller_output_path = os.path.join(output_folder, f"{original_name}_SELLER.jpg")
                cv2.imwrite(seller_output_path, seller_crop)

                with open(output_file_path, "a", encoding="utf-8") as file:
                    file.write("\n賣方統一編號：")

                seller_number = Recognition(seller_output_path, "NO")

            else:
                # 取得前 2 名匹配結果
                (conf1, (x1a, y1a, x2a, y2a)), (conf2, (x1b, y1b, x2b, y2b)) = top_matches

                # 判斷 Y 軸位置，較高的當「賣方」，較低的當「買方」
                if y1a < y1b:
                    seller_rect, buyer_rect = (x1a, y1a, x2a, y2a), (x1b, y1b, x2b, y2b)
                else:
                    seller_rect, buyer_rect = (x1b, y1b, x2b, y2b), (x1a, y1a, x2a, y2a)

                # 處理賣方
                sx1, sy1, sx2, sy2 = seller_rect
                seller_crop = original_image[sy1 - 5 : sy2 + 5, :]
                
                ############################# 把模板部分變白色 這樣就不會把o辨識成0 ##############################
                # 防止座標超出圖像邊界
                height, width = original_image.shape[:2]
                sy1_safe = max(sy1 - 5, 0)
                sy2_safe = min(sy2 + 5, height)
                sx1_safe = max(sx1, 0)
                sx2_safe = min(sx2, width)
                
                # 截取賣方影像
                seller_crop = original_image[sy1_safe:sy2_safe, :].copy()
                # 計算相對座標（裁切後）
                relative_y1 = sy1 - sy1_safe
                relative_y2 = sy2 - sy1_safe
                
                # 灰階影像，設為白色
                seller_crop[relative_y1:relative_y2, sx1_safe:sx2_safe] = 255
                ######################################################################################

                # 繪製賣方框（黃色）
                cv2.rectangle(finalImage, (0, sy1 - 5), (width, sy2 + 5), (255, 0, 0), 2)

                # 保存影像（賣方）
                seller_output_path = os.path.join(output_folder, f"{original_name}_SELLER.jpg")
                cv2.imwrite(seller_output_path, seller_crop)

                with open(output_file_path, "a", encoding="utf-8") as file:
                    file.write("\n賣方統一編號：")


                seller_number = Recognition(seller_output_path, "NO")

                # 處理買方
                bx1, by1, bx2, by2 = buyer_rect
                buyer_crop = original_image[by1 - 5 : by2 + 5, :]
                
                ############################# 把模板部分變白色 這樣就不會把o辨識成0 ##############################
                by1_safe = max(by1 - 5, 0)
                by2_safe = min(by2 + 5, original_image.shape[0])
                bx1_safe = max(bx1, 0)
                bx2_safe = min(bx2, original_image.shape[1])

                buyer_crop = original_image[by1_safe:by2_safe, :].copy()
                relative_y1 = by1 - by1_safe
                relative_y2 = by2 - by1_safe
                
                buyer_crop[relative_y1:relative_y2, bx1_safe:bx2_safe] = 255
                ######################################################################################

                # 繪製買方框（紫色）
                cv2.rectangle(finalImage, (0, by1 - 5), (width, by2 + 5), (255, 0, 0), 2)

                # 保存影像（買方）
                buyer_output_path = os.path.join(output_folder, f"{original_name}_BUYER.jpg")
                cv2.imwrite(buyer_output_path, buyer_crop)

                ######################################  k-means  ######################################
                # 讀取圖片
                image = cv2.imread(buyer_output_path)

                if image is None:
                    print("圖像路徑錯誤，請檢查！")
                    exit()

                # 轉換為灰階
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

                # 將圖像轉換為 2D 數據
                pixels = gray.reshape(-1, 1)

                # 使用 K-means 聚類 (k=2: 文字與背景)
                kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
                kmeans.fit(pixels)

                # 取得聚類中心與標籤
                centroids = kmeans.cluster_centers_.astype(int)
                labels = kmeans.labels_

                # 生成聚類圖像
                segmented_image = centroids[labels].reshape(gray.shape)

                # 將深色區域視為文字區域
                text_mask = (segmented_image == np.min(centroids)).astype(np.uint8) * 255

                # 找到文字區域的輪廓
                contours, _ = cv2.findContours(text_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                # 計算所有輪廓的中心位置
                centers = []
                for contour in contours:
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        centers.append((cx, cy))

                # 獲取圖片寬度
                img_height, img_width, _ = image.shape

                # 計算刪減區域
                if centers:
                    last_center_x = centers[-1][0]
                    #print(f"最後一個文字區域的中心點座標：({last_center_x}, {centers[-1][1]})")

                    # 計算 a
                    a = img_width - last_center_x
                    #print(f"a 值：{a}")

                    # 計算刪除範圍
                    delete_start_x = max(0, img_width - 2 * a)  # 確保不超出邊界

                    # 刪除右邊 2a 的區域（設為白色）
                    image[:, delete_start_x:] = (255, 255, 255)

                    #print(f"刪除範圍：從 X = {delete_start_x} 到 X = {img_width}")

                    # 保存刪減後的影像
                    cv2.imwrite(buyer_output_path, image)

                else:
                    print("未找到任何中心點，無法計算 a 值。")

                ######################################################################

                with open(output_file_path, "a", encoding="utf-8") as file:
                    file.write("\n買方統一編號：")

                buyer_number = Recognition(buyer_output_path, "NO")

                if buyer_number == seller_number or buyer_number == "*" or buyer_number == "": #賣方買方不會是同一個
                    buyer_number = "00000000"


    #匹配金額的
    #改 0409 本來 threshold=0.7
    def template_Money(image_path, template_folder, threshold=0.65, nms_threshold=0.9, output_folder=r"C:\seniorProject\LaiCode\two_bill\output\template"):
        global have_tax_amount

        # 讀取圖片
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        original_image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)  # 用於裁剪的原始圖片
        
        if image is None:
            #print(f"無法讀取圖像: {image_path}")
            return 0

        h, w = image.shape
        matched_areas = []  # 用於儲存已截圖的區域
        count = 1  # 初始值為 1，用於命名截圖檔案

        # 取得原圖的名稱，去掉副檔名
        original_name = os.path.splitext(image_name)[0]

        # 遍歷模板資料夾中的所有模板
        for template_name in os.listdir(template_folder):
            template_path = os.path.join(template_folder, template_name)

            if not template_name.lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            # 讀取模板圖像
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                print(f"無法讀取模板: {template_path}")
                continue

            # 模板匹配
            result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(result >= threshold)

            # 儲存匹配到的矩形框和信賴度
            all_rects = []
            all_confidences = []

            for pt in zip(*loc[::-1]):
                x, y = pt
                conf = result[y, x]
                rect = [x, y, x + template.shape[1], y + template.shape[0]]
                all_rects.append(rect)
                all_confidences.append(conf)

            # 非極大值抑制，避免重複匹配
            if len(all_rects) > 0:
                indices = cv2.dnn.NMSBoxes(all_rects, all_confidences, threshold, nms_threshold)

                # 如果有匹配的框
                if len(indices) > 0:
                    for i in indices.flatten():
                        x1, y1, x2, y2 = all_rects[i]

                        # 確保與已匹配的區域不重疊
                        overlap = False
                        for area in matched_areas:
                            prev_y1, prev_y2 = area
                            # 如果新的匹配框與已匹配框在 Y 軸上有重疊
                            if not (y2 < prev_y1 or y1 > prev_y2):
                                overlap = True
                                break

                        if overlap:
                            continue

                        # 儲存當前匹配的 Y 軸範圍
                        matched_areas.append((y1, y2))

                        # 判斷是否為模板1~3，根據模板名稱執行不同操作
                        if template_name in ["money1.jpg", "money3.jpg"]:
                            have_tax_amount = True

                        # 截圖整行（使用原始圖像）
                        line_top = max(0, y1 - 5)
                        line_bottom = min(h, y2 + 5)
                        cropped_line = original_image[line_top:line_bottom, :]
        
                        # 確保裁剪的圖片不是空的
                        if cropped_line.size > 0:

                            cropped_image_path = os.path.join(output_folder, f"{original_name}_Money_{count}.jpg")
                            cv2.imwrite(cropped_image_path, cropped_line)
                            #print(f"已保存截圖: {cropped_image_path}")

                            Recognition(cropped_image_path,"money")

                            # 匹配到的圖片數量加一
                            count += 1

                        ############################## 這裡是要畫框框的 ##############################
                        # 在圖片上繪製矩形，顏色為紅色，線條粗細為2
                        cv2.rectangle(finalImage, ( 0, y1-5), (width, y2+5), (0, 255, 0), 2)

        global max_Money
        #global have_tax_amount
        global total_amount
        global tax_free
        global tax_amount
        global rate


        output_file_path = r"C:\seniorProject\LaiCode\two_bill\two_output\data\data.txt"

        if have_tax_amount == True:
            output_message = ""
            result = math.ceil(max_Money * 0.95)  # 無條件進位
            output_message += "\n"
            output_message += f"銷售額：{result}"
            output_message += "\n"
            output_message += f"總計額：{max_Money}"
            #tax_free = result # 免稅銷售額
            tax_amount = result # 應稅銷售額 = 總計額 * 0.95
            rate = max_Money - result # 稅額 = 總計額 - 應稅銷售額

        else:
            output_message = ""
            #result = math.ceil(max_Money * 0.95)  # 無條件進位
            output_message += "\n"
            output_message += f"銷售額：{max_Money}"
            output_message += "\n"
            output_message += f"總計額：{max_Money}"
            tax_free = max_Money # 免稅銷售額 = 總計額


        total_amount = max_Money


        # 將結果寫入指定的文本檔案
        with open(output_file_path, "a", encoding="utf-8") as file:
            file.write(output_message)

    # 給傳統字軌用的 這跟電子上半用的一樣
    def RecognitionNumber(imageRecognition_path, *args):
        # 印出當前工作目錄
        #print(os.getcwd())

        # 拿到def外 不然會一直重複建構 GPU記憶體會爆!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # 建構yolo網路
        #Detect = darknet_me.Detect(r"./LaiCode\main/cfg/tt.data", r"C:\seniorProject\LaiCode\main\cfg/yolov4_tt.cfg", r"./LaiCode\main\cfg/yolov4_tt_last.weights")

        # YOLO辨識
        image = cv2.imread(imageRecognition_path)
        det_img, detections = Detect_1.image_detection(image, Detect_1.network, Detect_1.class_names, Detect_1.class_colors,thresh=0.1)#改0409

        # 自己設定的 [ 編號, 信心, (x, y, 寬, 高) ] detections陣列
        #print("原始 detections:", detections)

        # 取得檢測結果: 編號, 信心, (x, y, 寬, 高)
        boxes = []
        confidences = []
        class_ids = []
        
        print(args)
        for detection in detections:
            print(detection) # 印出所有的 detections，查看每個物件的類別、信心度和邊界框
            
            label, confidence, bbox = detection
            x, y, w, h = bbox
            if args == ("date",):
                if 0 <= int(label) <= 9: # 加入類別篩選條件：只處理 0~9 的檢測結果
                    boxes.append([int(x - w // 2), int(y - h // 2), int(w), int(h)])  # YOLO 的框是以中心點計算的
                    confidences.append(float(confidence))
                    class_ids.append(int(label))
            elif args == ("EN",):
                if 10 <= int(label) <= 35:  # 篩選條件：只處理 10~35 的檢測結果
                    boxes.append([int(x - w // 2), int(y - h // 2), int(w), int(h)])  # YOLO 的框是以中心點計算的
                    confidences.append(float(confidence))
                    class_ids.append(int(label))

            else:
                if 0 <= int(label) <= 9:
                    boxes.append([int(x - w // 2), int(y - h // 2), int(w), int(h)])  # YOLO 的框是以中心點計算的
                    confidences.append(float(confidence))
                    class_ids.append(int(label))

        print("-----")
        # 設定 NMS 閾值 #改 本來是 nms_threshold = 0.4  score_threshold=0.5
        nms_threshold = 0.1

        # 使用 OpenCV 的非極大值抑制
        indices = cv2.dnn.NMSBoxes(boxes, confidences, score_threshold=0.1, nms_threshold=nms_threshold)

        # 篩選出經過 NMS 處理的檢測結果
        filtered_detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                filtered_detections.append((class_ids[i], confidences[i], boxes[i]))


        # # 如果需要顯示圖片
        # cv2.imshow("YOLO Detection", det_img)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()

        ###########################################################################################################
        # 1. 使用 sorted 函數按照 x 座標從小到大排序
        sorted_detections = sorted(filtered_detections, key=lambda det: det[2][0])
        # print(sorted_detections[0])
        
        # if args == ("date",):
            
        #     if str(sorted_detections[0]).startswith('7'):  # 檢查第一個數字是不是7
        #         sorted_detections[0] = (1,sorted_detections[0])  # 改成1
        #     if str(sorted_detections[1]).startswith('7'):  # 檢查第一個數字是不是7
        #         sorted_detections[1] = (1,sorted_detections[1])  # 改成1
            
        #     if sorted_detections[0] == 7:  # 檢查前兩個數字是否是7 因為日期只有11x 不會有17x
        #         sorted_detections[0] = 1
        #     elif sorted_detections[1] == 7:
        #         sorted_detections[1] = 1

        # 自己設定的 [ 編號, 信心, (x, y, 寬, 高) ] detections陣列  排序好的
        print("左到右排好的 detections:", sorted_detections)

        # 設置閾值，X 座標小於該值的數字將被視為接近
        x_threshold = 100  # 根據實際情況調整該值

        # 2. 初始化變數
        amount_digits = []  # 用來記錄0~9的數字和它們的x座標
        max_detected = None
        label_x = None  # 用來記錄10~12的x座標（稅或金額）
        #print(args)
        # 3. 遍歷 sorted_detections
        for det in sorted_detections:
            label, confidence, bbox = det
            x, y, w, h = bbox

            # 將 label 轉換為整數進行比較
            label = int(label)

            if 0 <= label <= 35:
                # 將數字 10-35 映射到英文字母 A-Z
                if label >= 10:
                    num_to_english = {
                        10: "A", 11: "B", 12: "C", 13: "D", 14: "E", 15: "F", 16: "G", 17: "H",
                        18: "I", 19: "J", 20: "K", 21: "L", 22: "M", 23: "N", 24: "O", 25: "P",
                        26: "Q", 27: "R", 28: "S", 29: "T", 30: "U", 31: "V", 32: "W", 33: "X",
                        34: "Y", 35: "Z"
                    }
                    translated_label = num_to_english[label]  # 將數字轉換為字母
                else:
                    translated_label = str(label)  # 將 0-9 的數字轉換為字串

                amount_digits.append((translated_label, x))  # 將數字/字母和 x 座標記錄下來

            # # 當 label 為 10、11 或 12 時，表示偵測到 "稅" 或 "計" 或 "額"

            # elif (label == 10 or label == 11 or label == 12) and args == ("money",): #args 是要他確定是money的部分才做 不然就要提高我們的辨識精準度 因為有些有問題 EX:a4.jpg
            #     label_x = x  # 記錄稅或金額的 x 座標
            #     max_detected = True



            # 如果有偵測到數字，進行分組處理
        if amount_digits:
            # 按照 X 座標從小到大排序數字
            amount_digits.sort(key=lambda d: d[1])

            # 初始化分組變數
            groups = []
            current_group = [amount_digits[0]]  # 初始化第一組

            # 遍歷數字列表，將 X 座標接近的數字分為一組
            for i in range(1, len(amount_digits)):
                prev_x = amount_digits[i - 1][1]
                current_x = amount_digits[i][1]

                # # 如果當前數字和前一個數字的 X 座標差異小於閾值，則將它們分為一組
                # if abs(current_x - prev_x) < x_threshold:
                current_group.append(amount_digits[i])
            #     else:
            #         # 如果 X 座標差異大於閾值，則將當前組保存並開始新的分組
            #         groups.append(current_group)
            #         current_group = [amount_digits[i]]

            # # 最後一組也要保存
            # if current_group:
            #     groups.append(current_group)

            # # 找出包含最多數字的分組
            # largest_group = max(groups, key=len)

            # # 保留該分組中的數字，並刪除其他數字
            # amount_digits = largest_group

        # 4. 構建輸出的結果
        output_message = ""
        if amount_digits:
            amount = "".join([str(digit) for digit, _ in amount_digits])  # 將數字列表組合成字串

            global max_Money


            # 找最大的金額數字 去運算
            if max_detected:
                if max_Money < int(amount):
                    max_Money = int(amount)

            # 如果既沒有偵測到稅也沒有偵測到金額，只輸出累積的數字
            if not max_detected:
                output_message += f"{amount}"
                #print(f"{amount} ")  # 保留原有的 print
        else:
            output_message += ""
            #print("沒有符合條件的數字 ")  # 保留原有的 print

        # if len(output_message) == 2 or len(output_message) == 8:
        #     output_message += ""
        # else:
        #     output_message += "*"

        # 將結果寫入指定的文本檔案
        output_file_path = r"C:\seniorProject\LaiCode\two_bill\two_output\data\data.txt"
        with open(output_file_path, "a", encoding="utf-8") as file:
            file.write(output_message)
            
        if args == ("EN",): #字軌的英文部分
            output_message = output_message[:2]  # 只取前兩個元素
        if (args != ("EN",) and args != ("date",)): #都不是的話就是字軌的數字部分
            output_message = output_message[:8]  # 只取前兩個元素
        return output_message



    def Recognition(imageRecognition_path, *args):
        # 印出當前工作目錄
        #print(os.getcwd())

        # 拿到def外 不然會一直重複建構 GPU記憶體會爆!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # 建構yolo網路
        #Detect = darknet_me.Detect(r"./LaiCode\main/cfg/tt.data", r"C:\seniorProject\LaiCode\main\cfg/yolov4_tt.cfg", r"./LaiCode\main\cfg/yolov4_tt_last.weights")

        # YOLO辨識
        image = cv2.imread(imageRecognition_path)
        det_img, detections = Detect.image_detection(image, Detect.network, Detect.class_names, Detect.class_colors,thresh=0.25)#改0409
        
        # 自己設定的 [ 編號, 信心, (x, y, 寬, 高) ] detections陣列
        #print("原始 detections:", detections)

        # 取得檢測結果: 編號, 信心, (x, y, 寬, 高)
        boxes = []
        confidences = []
        class_ids = []
        
        print(args)
        for detection in detections:
            print(detection) # 印出所有的 detections，查看每個物件的類別、信心度和邊界框
            
            label, confidence, bbox = detection
            x, y, w, h = bbox
            boxes.append([int(x - w // 2), int(y - h // 2), int(w), int(h)])  # YOLO 的框是以中心點計算的
            confidences.append(float(confidence))
            class_ids.append(int(label))
            
        print("-----")

        # 設定 NMS 閾值 改0409 本來是nms_threshold = 0.4 core_threshold=0.5
        nms_threshold = 0.1

        # 使用 OpenCV 的非極大值抑制
        indices = cv2.dnn.NMSBoxes(boxes, confidences, score_threshold=0.1, nms_threshold=nms_threshold)

        # 篩選出經過 NMS 處理的檢測結果
        filtered_detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                filtered_detections.append((class_ids[i], confidences[i], boxes[i]))

        ###########################################################################################################
        # 1. 使用 sorted 函數按照 x 座標從小到大排序
        sorted_detections = sorted(filtered_detections, key=lambda det: det[2][0])

        # 自己設定的 [ 編號, 信心, (x, y, 寬, 高) ] detections陣列  排序好的
        #print("左到右排好的 detections:", sorted_detections)

        # 設置閾值，X 座標小於該值的數字將被視為接近
        x_threshold = 100  # 根據實際情況調整該值

        # 2. 初始化變數
        amount_digits = []  # 用來記錄0~9的數字和它們的x座標
        max_detected = None
        label_x = None  # 用來記錄10~12的x座標（稅或金額）
        #print(args)
        # 3. 遍歷 sorted_detections
        for det in sorted_detections:
            label, confidence, bbox = det
            x, y, w, h = bbox

            # 將 label 轉換為整數進行比較
            label = int(label)

            # 如果編號在 0~9 之間，將其加入金額數字列表
            if 0 <= label <= 9:
                amount_digits.append((label, x))  # 將數字和 x 座標記錄下來

            # 當 label 為 10、11 或 12 時，表示偵測到 "稅" 或 "計" 或 "額"

            if (label == 10 or label == 11 or label == 12) or args == ("money",): #args 是要他確定是money的部分才做 不然就要提高我們的辨識精準度 因為有些有問題 EX:a4.jpg
                label_x = x  # 記錄稅或金額的 x 座標
                max_detected = True

                if label == 10:
                    max_detected = False #改0409
                    global have_tax_amount
                    have_tax_amount = True
                    return 


        # 如果有偵測到數字，進行分組處理
        if amount_digits:
            # 按照 X 座標從小到大排序數字
            amount_digits.sort(key=lambda d: d[1])

            # 初始化分組變數
            groups = []
            current_group = [amount_digits[0]]  # 初始化第一組

            # 遍歷數字列表，將 X 座標接近的數字分為一組
            for i in range(1, len(amount_digits)):
                prev_x = amount_digits[i - 1][1]
                current_x = amount_digits[i][1]

                # 如果當前數字和前一個數字的 X 座標差異小於閾值，則將它們分為一組
                if abs(current_x - prev_x) < x_threshold:
                    current_group.append(amount_digits[i])
                else:
                    # 如果 X 座標差異大於閾值，則將當前組保存並開始新的分組
                    groups.append(current_group)
                    current_group = [amount_digits[i]]

            # 最後一組也要保存
            if current_group:
                groups.append(current_group)

            # 找出包含最多數字的分組
            largest_group = max(groups, key=len)

            # 保留該分組中的數字，並刪除其他數字
            amount_digits = largest_group

        # 4. 構建輸出的結果
        output_message = ""
        if amount_digits:
            amount = "".join([str(digit) for digit, _ in amount_digits])  # 將數字列表組合成字串

            global max_Money

            # 找最大的金額數字 去運算
            if max_detected:
                if max_Money < int(amount):
                    max_Money = int(amount)
                    return 0

            # 如果既沒有偵測到稅也沒有偵測到金額，只輸出累積的數字
            if not max_detected:
                output_message += f"{amount}"
                #print(f"{amount} ")  # 保留原有的 print
        else:
            output_message += ""
            #print("沒有符合條件的數字 ")  # 保留原有的 print

        # if args == ("NO",) and len(output_message) != 8:
        #     output_message += "*"

        # 將結果寫入指定的文本檔案
        output_file_path = r"C:\seniorProject\LaiCode\two_bill\two_output\data\data.txt"
        with open(output_file_path, "a", encoding="utf-8") as file:
            file.write(output_message)

        return output_message

        ###########################################################################################################

        # 顯示圖像
        #cv2.imshow("det_img", det_img)
        #cv2.waitKey(0)


    #主程式

    # 清空文件內容
    #output_file_path = r"C:\seniorProject\LaiCode\main\dataTemp\data.txt"
    #with open(output_file_path, "w", encoding="utf-8") as file:
    #    file.write("")  # 清空文件

    # 拿到def外 不然會一直重複建構 GPU記憶體會爆!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # 建構yolo網路
    #Detect = darknet_me.Detect(r"C:\seniorProject\LaiCode\main\cfg\tt.data", r"C:\seniorProject\LaiCode\main\cfg\yolov4_tt.cfg", r"C:\seniorProject\LaiCode\main\cfg\yolov4_tt_last.weights")

    # # 遍歷圖像資料夾中的所有圖像
    # for image_name in os.listdir(r"C:\seniorProject\LaiCode\main\img"):
    #     image_path = os.path.join(r"C:\seniorProject\LaiCode\main\img", image_name)

    #     if not image_name.lower().endswith((".png", ".jpg", ".jpeg")):
    #         continue



    with open(output_file_path, "a", encoding="utf-8") as file:
        file.write(f"檔案名稱：{image_name} ")  # 先寫名字~~ 會像是: a1 號碼 統編 電話 錢錢 然後換行

    finalImage = cv2.imread(image_path)   #存原圖 來畫框框

    start(image_path,image_name) #包含日期date 跟 號碼number

    #template_No_Tel(image_path, r"C:\seniorProject\LaiCode\two_bill\TemplateMatching\tel") #電話
    template_Money(image_path, r"C:\seniorProject\LaiCode\two_bill\TemplateMatching\Money") #稅 計 額
    template_No_Tel(image_path, r"C:\seniorProject\LaiCode\two_bill\TemplateMatching\No") #統編

    with open(output_file_path, "a", encoding="utf-8") as file:
        file.write("\n--------------------------------------------------\n")  # 換行

    datefilename = os.path.basename(image_path)  # 只取文件名部分
    # 打開圖像，這裡假設是從 PIL 讀取的
    save_path = os.path.join(r"C:\seniorProject\LaiCode\two_bill\two_output\finalimage", f"final_{datefilename}")
    # 把 "#存原圖 來畫框框" 這個存下來
    cv2.imwrite(save_path, finalImage)

    global finalpath
    finalpath = save_path

    # 手動清理 GPU 緩存
    #torch.cuda.empty_cache()

##########################################################################################################

#主程式開始

#建網路
#上半網路
Detect_1 = darknet_me.Detect(r"C:\seniorProject\LaiCode\two_bill\ele_cfg\top_cfg/tt.data",r"C:\seniorProject\LaiCode\two_bill\ele_cfg\top_cfg\yolov4_tt.cfg",r"C:\seniorProject\LaiCode\two_bill\ele_cfg\top_cfg/yolov4_tt_last.weights")
#傳統發票
Detect = darknet_me.Detect(r"C:\seniorProject\LaiCode\two_bill\cfg\tt.data", r"C:\seniorProject\LaiCode\two_bill\cfg\yolov4_tt.cfg", r"C:\seniorProject\LaiCode\two_bill\cfg\yolov4_tt_last.weights")
#電子發票
ele_Detect = darknet_me.Detect(r"C:\seniorProject\LaiCode\two_bill\ele_cfg\down_cfg\tt.data",r"C:\seniorProject\LaiCode\two_bill\ele_cfg\down_cfg\yolov4_tt.cfg", r"C:\seniorProject\LaiCode\two_bill\ele_cfg\down_cfg\yolov4_tt_last.weights")

# 清空文件內容
output_file_path = r"C:\seniorProject\LaiCode\two_bill\ele_output\out.txt"
with open(output_file_path, "w", encoding="utf-8") as file:
    file.write("")  # 清空文件

processed_files = set()

# 最大等待時間（秒）
max_wait_time = 10
wait_time = 0
main_val = 1

mysql_reset()
mysql_set_max_allowed_packet()  #set 1 over

start_time = time.time()  # 紀錄開始時間
print("開始執行程式...")

while wait_time < max_wait_time:
    new_image_detected = False

    # 遍歷圖像資料夾中的所有圖像
    for image_name in os.listdir(r"C:\seniorProject\LaiCode\two_bill\img"):
        image_path = os.path.join(r"C:\seniorProject\LaiCode\two_bill\img", image_name)


        word_track = ""
        date = 0
        seller_number = "00000000"
        buyer_number = "00000000"
        total_amount = 0
        tax_free = 0
        tax_amount = 0
        rate = 0
        finalpath = "Null"

        # 檢查是否為圖片且未處理過
        if image_name.lower().endswith((".png", ".jpg", ".jpeg")) and image_name not in processed_files:
            processed_files.add(image_name)  # 標記文件為已處理
            new_image_detected = True  # 偵測到新圖片
            
            #time.sleep(1)
            
            image = cv2.imread(image_path)

            # 獲取圖片寬度
            height, width = image.shape[:2]

            # 判斷寬度是否大於等於 750
            if width >= 750:
                print(f"{image_path}是電子發票")
                electronic_invoice(image_path, image_name)
                #mysql_connect(str(main_val),str(word_track),str(date),str(seller_number),str(buyer_number),str(total_amount),str(tax_free),str(tax_amount),str(rate),finalpath)    #寫進mysql資料庫
            else:
                print(f"{image_path}是傳統發票")
                have_tax_amount = False
                max_Money = 0 #來保存 在辨識裡面的最大數字 我要計算他的稅跟金額
                traditional_invoice(image_path, image_name)

            #tax_amount = total_amount - tax_free


            #要跑進去要掀開Xampp !!!!!!!!!!!
            #先按#掉而已(要測試時)!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

            mysql_connect(str(main_val),str(word_track),str(date),str(seller_number),str(buyer_number),str(total_amount),str(tax_free),str(tax_amount),str(rate),finalpath)    #寫進mysql資料庫
            #                 第幾個資料,       字軌,        日期,          賣方,              買方,            總金額,        免稅銷售額,     應稅銷售額,     稅額,  最終圖片(有畫框框)

            #os.system('pause')
            main_val += 1

    # 如果有新圖片，重置等待時間
    if new_image_detected:
        wait_time = 0
    else:
        # 否則，等待 1 秒並累加等待時間
        time.sleep(1)
        wait_time += 1

print("5 秒內沒有新圖片，結束程式")
print("程式執行完畢")
end_time = time.time()  # 結束時間
execution_time = end_time - start_time
print(f"程式總共執行了 {execution_time:.2f} 秒(包含等待結束的10秒)")

# 讀取 .txt 文件
txt_file = r"C:\seniorProject\LaiCode\two_bill\ele_output\out.txt"

with open(txt_file, "r", encoding="utf-8") as file:
    lines = file.read().split("--------------------------------------------------")

"""# 初始化 Excel 工作簿
wb = Workbook()
ws = wb.active
ws.title = "發票資料"

# 定義表頭
headers = ["檔案名稱", "字軌號碼", "銷售額", "總計額", "買方統一編號", "賣方統一編號"]
ws.append(headers)

# 處理每筆資料
for entry in lines:
    entry = entry.strip()
    if not entry:  # 跳過空行
        continue

    # 提取資料
    data = {}
    for line in entry.split("\n"):
        if "：" in line:  # 判斷是否為鍵值對
            key, value = line.split("：", 1)
            data[key.strip()] = value.strip()

    # 填入資料
    row = [
        data.get("檔案名稱", ""),
        data.get("字軌號碼", ""),
        data.get("銷售額", ""),
        data.get("總計額", ""),
        data.get("買方統一編號", ""),
        data.get("賣方統一編號", ""),
    ]
    ws.append(row)

# 保存為 Excel 文件
excel_file = r"C:\seniorProject\LaiCode\two_bill\two_output\data\data.xlsx"
wb.save(excel_file)
print(f"資料已成功寫入 {excel_file}")



# 開啟 Excel 文件
os.startfile(excel_file)"""
