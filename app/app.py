import os
from pathlib import Path
from functools import reduce

import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image
from matplotlib import cm

DATA_DIR = Path(__file__).absolute().parent / "data"


@st.cache_resource
def load_ann_codes():
    codes = {
        "Malignancy": {
            1: "Highly Unlikely",
            2: "Moderately Unlikely",
            3: "Indeterminate",
            4: "Moderately Suspicious",
            5: "Highly Suspicious",
        },
    }
    return codes


@st.cache_resource
def load_meta():
    scan_df = pd.read_csv(DATA_DIR / "scan_meta.csv")
    nod_df = pd.read_csv(DATA_DIR / "nodule_meta.csv")
    return scan_df, nod_df


@st.cache_resource
def load_raw_img(pid):
    img = np.load(DATA_DIR/pid/"scan.npy")
    return img


@st.cache_resource
def load_mask(pid):
    fnames = sorted((DATA_DIR/pid).glob('*_mask.npy'))
    masks = [np.load(fname) for fname in fnames]
    mask = reduce(np.logical_or, masks)
    return mask


@st.cache_resource
def load_nodule_img(pid, nid):
    img = np.load(DATA_DIR/pid/f"nodule_{nid:02d}_vol.npy")
    return img


@st.cache_resource
def get_img_slice(img, z, window=(-600, 1500)):
    # clip pixel values to desired window
    level, width = window
    img = np.clip(img, level-(width/2), level+(width/2))
    # normalize pixel values to 0-1 range
    img_min = img.min()
    img_max = img.max()
    img = (img - img_min) / (img_max - img_min)
    # convert to Pillow image for display
    img_slice = img[:, :, z]
    pil_img = Image.fromarray(np.uint8(cm.gray(img_slice)*255))
    return pil_img.convert('RGBA')

@st.cache_resource
def get_nod_slice(img, window=(-600, 1500)):
    # clip pixel values to desired window
    level, width = window
    img = np.clip(img, level-(width/2), level+(width/2))
    # normalize pixel values to 0-1 range
    img_min = img.min()
    img_max = img.max()
    img = (img - img_min) / (img_max - img_min)
    # convert to Pillow image for display
    z = int(img.shape[2]/2)
    img_slice = img[:, :, z]
    pil_img = Image.fromarray(np.uint8(cm.gray(img_slice)*255))
    return pil_img.convert('RGBA')


@st.cache_resource
def get_overlay():
    arr = np.zeros((512, 512, 4)).astype(np.uint8)
    arr[:, :, 1] = 128
    arr[:, :, 3] = 128
    overlay = Image.fromarray(arr, mode='RGBA')
    return overlay


@st.cache_resource
def get_mask_slice(mask, z):
    mask_slice = (mask[:, :, z]*96).astype(np.uint8)
    mask_img = Image.fromarray(mask_slice, mode='L')
    return mask_img


scan_df, nod_df = load_meta()
scan = scan_df.iloc[0]
pid = scan.PatientID
img_arr = load_raw_img(pid)
mask_arr = load_mask(pid)

st.header("Selected case for lung cancer detection application")

st.subheader("Patient information")

st.write("**Patient ID:**", scan.PatientID)
st.write("**Diagnosis:**", "Malignant, primary lung cancer")
st.write("**Diagnosis method:**", "Biopsy")

st.subheader(f"CT scan")

img_placeholder = st.empty()

col1, col2 = st.columns(2)

with col1:
    st.write("**Pixel spacing**")
    st.write(f"x: {scan.PixelSpacing:.2f} mm")
    st.write(f"y: {scan.PixelSpacing:.2f} mm")
    st.write(f"z: {scan.SliceSpacing:.2f} mm")
    st.write("**Device**")
    st.write(f"{scan.ManufacturerModelName} (by {scan.Manufacturer})")

with col2:
    overlay_nodules = st.checkbox("Show nodule overlay", value=True)
    z = st.slider("Slice:", min_value=1,
                  max_value=img_arr.shape[2], value=int(img_arr.shape[2]/2))
    level = st.number_input("Window level:", value=-600)
    width = st.number_input("Window width:", value=1500)

img = get_img_slice(img_arr, z-1, window=(level, width))

if overlay_nodules:
    mask = get_mask_slice(mask_arr, z-1)
    overlay = get_overlay()
    ct = Image.composite(overlay, img, mask)
    img_placeholder.image(ct, use_column_width=True)
else:
    img_placeholder.image(img, use_column_width=True)

st.subheader("Detected nodules")

codes = load_ann_codes()

for index, nodule in nod_df.iterrows():
    st.write(f"**Nodule #{nodule.NoduleID}**")
    col1, col2, col3 = st.columns([1, 2, 3])
    with col1:
        img_arr = load_nodule_img(pid, nodule.NoduleID)
        img = get_nod_slice(img_arr)
        st.image(img)
    with col2:
        st.write(f"Diameter: {nodule.Diameter:.2f}mm")
        st.write(f"Area: {nodule.SurfaceArea:.2f}mm²")
        st.write(f"Volume: {nodule.Volume:.2f}mm³")
    with col3:
        st.write(
            f"Pred. malignancy: {codes['Malignancy'][nodule.Malignancy]}")
