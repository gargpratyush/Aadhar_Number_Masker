import matplotlib.pyplot as plt
import numpy as np
import cv2
import pandas as pd
from sklearn.metrics import jaccard_score
from pathlib import Path
import os
import re
import argparse
import pytesseract
from tqdm import tqdm
from test import *  

parser = argparse.ArgumentParser(description='CRAFT Text Detection')
parser.add_argument('--cuda', default=False, type=str2bool, help='Use cuda for inference')
parser.add_argument('--test_folder', default='./images/', type=str, help='folder path to input images')
parser.add_argument('--output_folder', default='./output/', type=str, help='folder path to output images')

args = parser.parse_args()

def dist(a,b,c,d): #Calculates the distance between (a,b) and (c,d)
    return np.sqrt((a-c)**2 + (b-d)**2)

def scale_image(img, scale_factor): #Scale factor is percent of original size e.g 0.3
    width = max(int(img.shape[1] * scale_factor),1)
    height = max(int(img.shape[0] * scale_factor),1)
    dim = (width, height)
    
    # resize image
    resized = cv2.resize(img, dim, interpolation = cv2.INTER_AREA)
    return resized

def crop_image(img, points): #Crops the image to required pplygon
    height = img.shape[0]
    width = img.shape[1]
    
    #Creating a binary mask over the cropped area
    mask_img = np.zeros((height, width), dtype=np.uint8)
    cv2.fillPoly(mask_img, points, (255))
    
    
    #Removing background outside of crop
    res = cv2.bitwise_and(img,img,mask = mask_img)
    rect = cv2.boundingRect(points) # returns (x,y,w,h) of the rect
    
    #Cropping Image
    crop = res[rect[1]: rect[1] + rect[3], rect[0]: rect[0] + rect[2]]
    
    return crop

def tesseract_preprocess(img):
    
    height = img.shape[0]
    scale_factor = 30.0/height #Scales the image to 30 pixels, ideal size for tesseract
    
    scaled = scale_image(img, scale_factor)
            
    try:
        gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(gray, 97, 255, cv2.THRESH_BINARY)[1]
        return gray, thresh
    except:
        return scaled, scaled #To avoid Occasional random cv2 error
    
def num_length(string):
    nums = re.sub('[^0-9?TBaAZ$egiG]','', string) #Removing non-numeric characters. However, include characters like ?  
    return len(nums)                              #that tesseract commonly interprets numbers as

def aspect_ratio(a,b,c,d,e,f,g,h):
    def dist(a,b,c,d):
        return np.sqrt((a-c)**2 + (b-d)**2)
    ar = dist(a,b,c,d)/dist(c,d,e,f) #Checking Aspect Ratio
    return ar

def ar_check(ar): #Checks if the crop falls in possible dimensions. Otherwise, we can skip that crop and speed up process
    if 1.65<=ar<=5.75: #Dimensions that we need to check
        return True
    else:
        return False
    
def mask_number(img, points): #Masks the image at the given points
    cv2.fillPoly(img, points, (0,0,0))
    return

def neighbouring_boxes(pts1, pts2): #Checks if two boxes are next to each other as a function of box length and width
    
    v_distance = dist(pts1[0][0][0], pts1[0][0][1], pts1[0][3][0], pts1[0][3][1])
    h_distance = dist(pts1[0][0][0], pts1[0][0][1], pts1[0][1][0], pts1[0][1][1])
    if (abs(pts1[0][0][1]-pts2[0][0][1])<=0.75*v_distance) and (abs(pts1[0][0][0]-pts2[0][0][0])<=1.35*h_distance):
        return True
    else:
        return False
    
def process_image(img, file_name):
    
    pts_list = []
        
    with open(r"./result/res_"+os.path.splitext(file_name)[0]+".txt", "r") as filestream:        
            for line in filestream:
                currentline = line.split(",")
                try:
                    a,b,c,d,e,f,g,h=currentline #Reads the bounding box coordinates from CRAFT txt file
                except:
                    continue #Skips blank lines in txt file

                a,b,c,d,e,f,g,h=int(a),int(b),int(c),int(d),int(e),int(f),int(g),int(h)

                points = np.array([[[a,b],[c,d],[e,f],[g,h]]])

                ar = aspect_ratio(a,b,c,d,e,f,g,h)

                if not ar_check(ar): #If crop doesn't fall in required dimensions, skip it
                    continue

                crop = crop_image(img, points) #Crops the image


                gray1, thresh1 = tesseract_preprocess(crop)#Preprocesses, giving us gray and threshold images
            
            #We need gray and thresh images bcuz in some cases tesseract is able to read thresh easier while in others
            #It is able to read grayscale images easier. Hence, we pass both through tesseract and compare generated strings

#                 #Debug
#                 print(ar)
#                 cv2.imshow('Prepped',gray1)
#                 cv2.waitKey(0)
#                 #Debug End
        


                string1 = pytesseract.image_to_string(gray1,lang='eng',config='--psm 8 --oem 3')
                string2 = pytesseract.image_to_string(thresh1,lang='eng',config='--psm 8 --oem 3')

                string = string1 if num_length(string1)>num_length(string2) else string2 #Choosing the better string of gray or thresh

                #Debug
#                 if num_length(string1)>num_length(string2):
#                     print(string1)
#                     cv2.imshow('Gray', gray1)
#                     cv2.waitKey(0)
#                 else:
#                     print(string2)
#                     cv2.imshow('Thresh',thresh1)
#                     cv2.waitKey(0)
                #Debug End

                length = num_length(string)

                if len(re.sub('[^0-9]','', string))<2: #Skip it if it has less than two numbers
                    continue

                if length==8 or 11<=length<=13: #Masks automatically if 8 or 12 integers are present indicating Aadhaar no

                        #Debug
#                         print(length, ", ",string)
#                         cv2.imshow('Confirmed',prepped)
#                         cv2.waitKey(0)
                        #Debug End

                    mask_number(img, points)

                elif 3<=length<12: #In other cases less than 12, it gets appended to list to compare with other nearby clusters of pts
                    pts_list.append(points)

                    #Debug
        #                 print(length, ", ",string)
        #                 cv2.imshow('Sidelined',prepped)
        #                 cv2.waitKey(0)
                    #Debug End

    for index, pts1 in enumerate(pts_list):
        if len(pts_list)==1:
            break
        for pts2 in pts_list[index+1:]:
            if neighbouring_boxes(pts1, pts2):
                mask_number(img, pts1)
                mask_number(img, pts2)

                #Debug
#                     print(pts1[0][0][0], pts1[0][0][1], pts2[0][0][0], pts2[0][0][1])
#                     cv2.imshow('Masked', img)
#                     cv2.waitKey(0)
                #Debug End

        #Debug
#         cv2.imshow('Masked', img)
#         cv2.waitKey(0)
        #Debug End

    return img
    



if __name__ == '__main__':

    call_test(test_folder=args.test_folder,cuda=args.cuda) #Generating CRAFT Text Bounding Boxes
    
    print("CRAFT Box Detection Completed")
  
    #path_length=len(args.test_folder)
#   if (args.test_folder[-1]!='/'):
#     path_length=path_length+1
#   if (args.output_folder[-1]!='/'):
#     args.output_folder=args.output_folder+"/"    
#   paths=[]
#   for dirname, _, filenames in os.walk(args.test_folder):
#     for filename in filenames:
#         paths.append(os.path.join(dirname, filename))
#   try:
#     os.mkdir(args.output_folder)
#   except:
#     pass
    
    try:
        os.mkdir(args.output_folder) #Ensuring output directory exists
    except:
        pass
    
    if (args.test_folder[-1]!='/'):
        args.test_folder=args.test_folder+"/"
    if (args.output_folder[-1]!='/'):
        args.output_folder=args.output_folder+"/"
        
  
    pbar = tqdm(os.listdir(args.test_folder))
    
    for file_name in pbar:
        IMAGE_PATH = args.test_folder+file_name
        
        try:
            img = cv2.imread(IMAGE_PATH, cv2.IMREAD_UNCHANGED)
            height = img.shape[0]
            
        except:
            continue
            
        masked_img = process_image(img, file_name)
                                  
#     mean = np.mean(area_list)
#     std = np.std(area_list)
#     for i in range(len(num_list)):
#       (a,b,c,d,e,f,g,h) = num_list[i]
#       area = area_list[i]
#       if len(num_list)>3 and (((area-mean)/std)>2 or ((area-mean)/std)<-1):
#         continue
#       points = np.array([[[a,b],[c,d],[e,f],[g,h]]])
#       cv2.fillPoly(image, points, (0,0,0))
        
        cv2.imwrite(args.output_folder+"masked_"+file_name, masked_img)
        
    print("Masked Images Generated")
