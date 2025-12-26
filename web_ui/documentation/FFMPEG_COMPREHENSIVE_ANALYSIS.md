# EXHAUSTIVE FFMPEG DOCUMENTATION ANALYSIS
## For Termivoxed Video Editor Application

**Source:** /Users/santhu/Downloads/SubsGen2/console_video_editor/web_ui/documentation/ffmpeg/ffmpeg-all
**Total Lines:** 41,593 lines
**Analysis Date:** 2025-12-14

---

## TABLE OF CONTENTS

1. [Audio Filters (122+ filters)](#audio-filters)
2. [Video Filters (290+ filters)](#video-filters)
3. [Complex Filtergraph Syntax](#complex-filtergraphs)
4. [Stream Selection and Mapping](#stream-selection)
5. [Time-Based Operations](#time-operations)
6. [Video Scaling, Padding, Overlay](#video-manipulation)
7. [Text and Subtitle Burning](#text-subtitles)
8. [Encoding Options and Quality](#encoding-quality)
9. [Container Formats](#container-formats)
10. [Hardware Acceleration](#hardware-acceleration)
11. [Multi-Input Handling](#multi-input)
12. [Advanced Professional Features](#advanced-features)

---

## 1. AUDIO FILTERS (122+ Filters)

### 1.1 Audio Processing Filters

**Compression & Dynamics:**
- `acompressor` - Audio compressor with attack, release, ratio, threshold
- `agate` - Audio gate/expander
- `adrc` - Audio dynamic range compression
- `adynamicequalizer` - Dynamic equalizer
- `alimiter` - Audio limiter to prevent clipping
- `apsyclip` - Psychoacoustic clipper
- `compand` - Compress/expand audio dynamic range
- `mcompand` - Multiband compand
- `sidechaincompress` - Sidechain compression
- `sidechaingate` - Sidechain gating

**Equalization & Filtering:**
- `equalizer` - Apply two-pole peaking equalization (EQ) filter
- `anequalizer` - Apply high-order audio parametric multi band equalizer
- `firequalizer` - Finite Impulse Response equalizer
- `superequalizer` - Apply 18-band graphic equalizer
- `bass` / `lowshelf` - Boost/cut bass frequencies
- `treble` / `highshelf` - Boost/cut treble frequencies
- `tiltshelf` - Apply tilt shelf filter
- `bandpass` - Apply two-pole Butterworth band-pass filter
- `bandreject` - Apply two-pole Butterworth band-reject filter
- `highpass` - Apply high-pass filter
- `lowpass` - Apply low-pass filter
- `allpass` - Apply two-pole all-pass filter
- `biquad` - Apply biquad IIR filter with given coefficients

**Noise Reduction & Cleanup:**
- `afftdn` - Denoise audio using FFT
- `afwtdn` - Denoise audio using wavelets
- `anlmdn` - Reduce broadband noise using Non-Local Means
- `arnndn` - Reduce noise using Recurrent Neural Networks
- `adeclick` - Remove impulsive noise from audio
- `adeclip` - Remove clipped samples from audio
- `adenorm` - Remedy denormal floating point audio
- `dcshift` - Apply DC shift to audio

**Time & Pitch:**
- `atempo` - Adjust audio tempo (0.5 to 100.0)
- `afreqshift` - Apply frequency shift
- `aphaseshift` - Apply phase shift
- `rubberband` - Time-stretching and pitch-shifting

**Reverb & Delay:**
- `aecho` - Add echoing to audio
- `adelay` - Delay audio streams
- `compensationdelay` - Compensate for audio delay

**Spatial & Stereo:**
- `stereotools` - Apply stereo tools
- `stereowiden` - Apply stereo widening effect
- `extrastereo` - Increase stereo separation
- `surround` - Apply surround sound  
- `headphone` - Apply binaural audio effect
- `sofalizer` - Spatialize audio using SOFA files
- `bs2b` - Bauer stereo to binaural transformation
- `crossfeed` - Apply crossfeed between channels
- `earwax` - Widen stereo field for headphones
- `haas` - Apply Haas stereo enhancer

**Channel Operations:**
- `channelmap` - Remap audio channels
- `channelsplit` - Split audio to per-channel streams
- `amerge` - Merge multiple audio streams into single multi-channel
- `join` - Join multiple audio streams
- `pan` - Remix channels with coefficients

**Effects:**
- `chorus` - Add chorus effect
- `flanger` - Apply flanging effect
- `phaser` / `aphaser` - Apply phasing effect
- `tremolo` - Apply tremolo effect
- `vibrato` - Apply vibrato effect
- `crystalizer` - Apply crystalizer effect
- `dialoguenhance` - Enhance dialogue
- `deesser` - De-ess audio
- `aexciter` - Add harmonic excitation
- `asubboost` - Boost subwoofer frequencies
- `asubcut` - Cut subwoofer frequencies
- `virtualbass` - Apply virtual bass enhancement

**Volume & Mixing:**
- `volume` - Change input volume
- `volumedetect` - Detect audio volume
- `loudnorm` - EBU R128 loudness normalization
- `dynaudnorm` - Dynamic Audio Normalizer
- `speechnorm` - Speech Normalizer
- `amix` - Mix multiple audio inputs into single output
- `acrossfade` - Cross fade two audio streams

**Analysis:**
- `astats` - Show time domain statistics
- `aspectralstats` - Show frequency domain statistics
- `apsnr` - Measure audio PSNR (Peak Signal-to-Noise Ratio)
- `asdr` - Measure Audio Signal-to-Distortion Ratio
- `asisdr` - Measure Audio SI-SDR
- `drmeter` - Measure dynamic range
- `ebur128` - EBU R128 scanner
- `silencedetect` - Detect silence
- `ashowinfo` - Show line containing audio frame info

**Filtering:**
- `afir` - Apply Finite Impulse Response filter
- `aiir` - Apply Infinite Impulse Response filter
- `afftfilt` - Apply arbitrary filtering in frequency domain
- `anlmf` / `anlms` - Apply Normalized Least Means Filter/Square
- `arls` - Apply Recursive Least Squares filter

**Utility:**
- `aformat` - Convert input to specific sample formats
- `aresample` - Resample audio to specified parameters
- `asetnsamples` - Set number of samples per audio frame
- `asetrate` - Change sample rate without resampling
- `atrim` - Pick one continuous section from input
- `aloop` - Loop audio samples
- `areverse` - Reverse audio
- `apad` - Pad audio with silence
- `silenceremove` - Remove silence from audio
- `acopy` - Copy audio stream unchanged
- `anull` - Pass audio source unchanged to output

### 1.2 Audio Sources
- `aevalsrc` - Generate audio from expression
- `anoisesrc` - Generate noise audio signal
- `anullsrc` - Null audio source
- `sine` - Generate sine wave
- `flite` - Text-to-speech using libflite

### 1.3 Audio Evaluation
- `aeval` - Filter using per-sample expressions
- `axcorrelate` - Cross-correlate two audio streams

---

## 2. VIDEO FILTERS (290+ Filters)

### 2.1 Video Scaling & Resizing
- `scale` - Scale video to specified size with various algorithms
  - Syntax: `scale=width:height:flags=algorithm`
  - Algorithms: bilinear, bicubic, lanczos, spline, neighbor, area, etc.
  - Supports expressions: `scale=iw/2:ih/2` (half size)
- `zscale` - Scale using z.lib (high quality)
- `scale_cuda` - GPU-accelerated scaling (CUDA)
- `scale_npp` - NVIDIA Performance Primitives scaling
- `scale_vt` - VideoToolbox scaling (macOS)
- `scale2ref_npp` - Scale based on reference video

### 2.2 Cropping & Padding
- `crop` - Crop video to specified dimensions
  - Syntax: `crop=w:h:x:y`
  - Supports expressions: `crop=in_w/2:in_h/2:in_w/4:in_h/4`
- `cropdetect` - Auto-detect crop size
- `pad` - Add padding to video
  - Syntax: `pad=width:height:x:y:color`
- `pad_cuda` - GPU padding
- `pad_opencl` - OpenCL padding
- `pad_vaapi` - VAAPI padding
- `fillborders` - Fill borders of frame

### 2.3 Overlay & Compositing
- `overlay` - Overlay one video on top of another
  - Syntax: `overlay=x:y:enable='expression'`
  - Supports blend modes, alpha blending
- `overlay_cuda` - GPU overlay
- `overlay_opencl` - OpenCL overlay  
- `overlay_vaapi` - VAAPI overlay
- `overlay_vulkan` - Vulkan overlay
- `blend` - Blend two video frames (28+ blend modes)
- `blend_vulkan` - Vulkan blending
- `tblend` - Temporal blend

### 2.4 Color Manipulation
- `eq` - Adjust brightness, contrast, gamma, saturation
- `hue` - Adjust hue and saturation
- `colorbalance` - Adjust color balance
- `colorchannelmixer` - Adjust colors by mixing channels
- `colorcontrast` - Adjust color contrast
- `colorcorrect` - Adjust color white balance/temperature
- `colorize` - Colorize video
- `colorlevels` - Adjust video input/output levels
- `colorspace` - Convert between colorspaces
- `colorspace_cuda` - GPU colorspace conversion
- `colortemperature` - Adjust color temperature
- `curves` - Adjust color curves
- `pseudocolor` - Map color/gray values to pseudo colors
- `selectivecolor` - Apply CMYK adjustments to specific colors
- `vibrance` - Boost/reduce saturation of least saturated colors
- `lut` / `lutrgb` / `lutyuv` - Apply lookup tables
- `lut1d` - Apply 1D LUT
- `lut3d` - Apply 3D LUT  
- `haldclut` - Apply Hald CLUT

### 2.5 Chroma Keying & Transparency
- `chromakey` - Chroma keying (green screen)
- `chromakey_cuda` - GPU chroma keying
- `colorkey` - Remove color
- `colorkey_opencl` - OpenCL colorkey
- `colorhold` - Remove all color except specified
- `chromahold` - Turn specific color range to gray
- `hsvkey` - HSV color keying
- `hsvhold` - HSV color hold
- `lumakey` - Luma keying
- `backgroundkey` - Remove background
- `despill` - Despill (remove) color
- `alphaextract` - Extract alpha channel
- `alphamerge` - Merge alpha channel
- `premultiply` - Apply alpha premultiplication
- `unpremultiply` - Remove premultiplied alpha

### 2.6 Deinterlacing
- `yadif` - Yet Another Deinterlacing Filter
- `yadif_cuda` - GPU deinterlacing
- `bwdif` - Bob Weaver Deinterlacing Filter
- `bwdif_cuda` / `bwdif_vulkan` - GPU bwdif
- `w3fdif` - Weston 3 Field Deinterlacing Filter
- `kerndeint` - Kernel deinterlacing
- `estdif` - Edge Slope Tracing Deinterlacing Filter
- `fieldmatch` - Field matching for inverse telecine
- `detelecine` - Apply inverse telecine
- `interlace` / `interlace_vulkan` - Interlace filter

### 2.7 Denoising & Cleanup
- `hqdn3d` - High quality 3D denoiser
- `nlmeans` - Non-local means denoiser
- `nlmeans_opencl` / `nlmeans_vulkan` - GPU denoising
- `atadenoise` - Adaptive temporal averaging denoiser
- `fftdnoiz` - Denoise using FFT
- `dctdnoiz` - Denoise using DCT
- `vaguedenoiser` - Vague denoiser
- `owdenoise` - Overcomplete wavelet denoiser
- `removegrain` - Remove grain
- `chromanr` - Chroma noise reduction
- `bm3d` - Block-Matching 3D denoiser

### 2.8 Sharpening & Blurring
- `unsharp` - Sharpen/blur video
- `unsharp_opencl` - OpenCL unsharp
- `cas` - Contrast Adaptive Sharpening
- `sharpen_npp` - NVIDIA sharpening
- `boxblur` - Apply box blur
- `boxblur_opencl` - OpenCL boxblur
- `avgblur` - Apply average blur
- `avgblur_opencl` / `avgblur_vulkan` - GPU avgblur
- `gblur` - Apply Gaussian blur
- `gblur_vulkan` - Vulkan Gaussian blur
- `dblur` - Directional blur
- `smartblur` - Smart blur
- `bilateral` - Bilateral filter
- `bilateral_cuda` - GPU bilateral
- `varblur` - Variable blur
- `yaepblur` - Yet another edge preserving blur
- `guided` - Guided filter

### 2.9 Edge Detection
- `edgedetect` - Detect/mark edges
- `sobel` - Sobel edge detection
- `sobel_opencl` - OpenCL Sobel
- `prewitt` - Prewitt edge detection
- `prewitt_opencl` - OpenCL Prewitt
- `roberts` - Roberts edge detection
- `roberts_opencl` - OpenCL Roberts
- `scharr` - Scharr edge detection
- `kirsch` - Kirsch edge detection

### 2.10 Stabilization
- `vidstabdetect` - Extract and analyze camera movements (pass 1)
- `vidstabtransform` - Apply video stabilization (pass 2)
- `deshake` - Stabilize shaky video
- `deshake_opencl` - OpenCL deshake

### 2.11 Motion & Frame Rate
- `fps` - Convert to constant frame rate
- `framerate` - Upconvert frame rate with motion interpolation
- `minterpolate` - Frame interpolation
- `framestep` - Select one frame every N frames
- `mestimate` - Estimate motion vectors
- `mpdecimate` - Drop duplicate frames
- `decimate` - Drop duplicated frames at specified rate
- `deflicker` - Remove temporal frame luminance variations
- `dejudder` - Remove judder by duplicating frames
- `fieldmatch` - Field matching filter
- `pullup` - Pulldown reversal filter

### 2.12 Drawing & Graphics
- `drawtext` - Draw text strings or text from file
  - Rich text formatting, timecode, metadata
  - Expressions for dynamic text
- `drawbox` - Draw colored boxes
- `drawbox_vaapi` - VAAPI drawbox
- `drawgrid` - Draw grid
- `drawgraph` - Draw values/metrics as graph
- `qrencode` - Generate QR code
- `qrencodesrc` - QR code source

### 2.13 Subtitle/Caption Handling
- `ass` - Render ASS subtitles
- `subtitles` - Render text subtitles (ASS/SSA/SRT)
- `readeia608` - Read EIA-608 closed captions
- `readvitc` - Read vertical interval timecode

### 2.14 Transformations
- `transpose` - Transpose and rotate video
- `transpose_npp` / `transpose_vt` / `transpose_vulkan` - GPU transpose
- `rotate` - Rotate video by arbitrary angle
- `hflip` - Flip horizontally
- `hflip_vulkan` - Vulkan hflip
- `vflip` - Flip vertically
- `vflip_vulkan` - Vulkan vflip
- `flip_vulkan` - Flip both directions
- `perspective` - Correct perspective
- `lenscorrection` - Apply lens correction
- `lensfun` - Apply lens correction using lensfun library
- `shear` - Shear transform
- `tiltandshift` - Apply tilt and shift

### 2.15 Fading & Transitions
- `fade` - Fade in/out
- `xfade` - Cross fade between inputs (40+ transition types)
- `xfade_opencl` - OpenCL xfade
- `acrossfade` - Audio cross fade

### 2.16 Temporal Filters
- `tmix` - Mix successive frames
- `tmedian` - Temporal median filter
- `tmidequalizer` - Temporal midway equalizer

### 2.17 Quality Metrics
- `psnr` - Calculate PSNR between two videos
- `ssim` - Calculate SSIM between two videos  
- `xpsnr` - Calculate extended PSNR
- `libvmaf` - Calculate VMAF score
- `libvmaf_cuda` - GPU VMAF
- `identity` - Calculate identity score
- `msad` - Mean Sum of Absolute Differences
- `corr` - Correlation
- `vif` - Visual Information Fidelity

### 2.18 Stacking & Tiling
- `hstack` - Stack inputs horizontally
- `hstack_qsv` / `hstack_vaapi` - GPU hstack
- `vstack` - Stack inputs vertically  
- `vstack_qsv` / `vstack_vaapi` - GPU vstack
- `xstack` - Stack inputs in custom layout
- `xstack_qsv` / `xstack_vaapi` - GPU xstack
- `tile` - Tile multiple frames into mosaic
- `untile` - Decompose tiled image

### 2.19 Format Conversion
- `format` - Convert pixel format
- `noformat` - Force libavfilter not to use specified formats
- `fps` - Convert frame rate
- `setdar` / `setsar` - Set display/sample aspect ratio
- `setfield` - Force field for Frame
- `fieldorder` - Set field order
- `separatefields` - Split interlaced into fields
- `weave` / `doubleweave` - Weave fields into frames

### 2.20 Advanced Color Grading
- `colormatrix` - Convert color matrix
- `colorspace` - Convert colorspace
- `tonemap` - Tone mapping for HDR
- `tonemap_opencl` / `tonemap_vaapi` - GPU tonemap
- `zscale` - Advanced scaling with HDR/colorspace
- `normalize` - Normalize RGB video
- `grayworld` - Gray world color correction
- `greyedge` - Grey edge color correction

### 2.21 Analysis & Scopes
- `histogram` - Compute/draw histogram
- `thistogram` - Compute/draw temporal histogram
- `waveform` - Video waveform monitor
- `vectorscope` - Video vectorscope
- `oscilloscope` - 2D video oscilloscope
- `ciescope` - Video CIE scope
- `showinfo` - Show textual frame info
- `signalstats` - Generate statistics
- `blackdetect` - Detect black frames/segments
- `blackframe` - Detect black frames
- `freezedetect` - Detect frozen video
- `blurdetect` - Detect blur in video
- `blockdetect` - Detect blocks in video
- `idet` - Interlace detection
- `scdet` - Scene change detection
- `siti` - Spatial Info/Temporal Info

### 2.22 Special Effects
- `geq` - Generic equation per-pixel filter
- `lut` - Arbitrary lookup table
- `convolution` - Apply convolution 3x3 or 5x5 matrix
- `convolution_opencl` - OpenCL convolution
- `convolve` - Convolve first video with second
- `deconvolve` - Deconvolve first video with second
- `morpho` - Morphological operations
- `erosion` - Erode video
- `erosion_opencl` - OpenCL erosion
- `dilation` - Dilate video
- `dilation_opencl` - OpenCL dilation
- `deflate` - Deflate video
- `inflate` - Inflate video
- `pixelize` - Pixelize video
- `noise` - Add noise
- `datascope` - Video data analysis
- `oscilloscope` - 2D video oscilloscope
- `v360` - Convert 360 projection (equirectangular, cube, etc.)
- `zoompan` - Apply zoom/pan effect
- `scroll` - Scroll input video
- `stereo3d` - Convert between stereoscopic formats

### 2.23 Logo & Watermark
- `delogo` - Remove logo
- `removelogo` - Remove logo using mask
- `addroi` - Add region of interest

### 2.24 Advanced Processing
- `sr` - Super-resolution using DNN
- `sr_amf` - AMD super-resolution
- `dnn_processing` - Generic DNN processing
- `dnn_classify` - DNN-based classification
- `dnn_detect` - DNN-based detection
- `libplacebo` - High-quality GPU processing (HDR, scaling, etc.)

### 2.25 Frame Selection & Manipulation
- `select` - Select frames based on expression
- `trim` - Pick continuous section
- `loop` - Loop video frames
- `reverse` - Reverse video
- `shuffleframes` - Shuffle frames
- `shufflepixels` - Shuffle pixels
- `shuffleplanes` - Shuffle planes
- `extractplanes` - Extract color planes
- `mergeplanes` - Merge planes
- `swapuv` - Swap U and V planes
- `rgbashift` - Shift RGBA components

### 2.26 Utility Filters
- `copy` - Copy input unchanged
- `null` - Pass video unchanged
- `showpalette` - Display palette
- `thumbnail` - Select most representative frame
- `thumbnail_cuda` - GPU thumbnail
- `find_rect` - Find rectangle
- `cover_rect` - Cover rectangle
- `swaprect` - Swap rectangles
- `remap` - Remap pixels
- `displace` - Displace pixels

### 2.27 Hardware-Accelerated Filters

**CUDA:**
- bilateral_cuda, chromakey_cuda, overlay_cuda, pad_cuda, scale_cuda, thumbnail_cuda, yadif_cuda

**OpenCL:**
- avgblur_opencl, boxblur_opencl, colorkey_opencl, convolution_opencl, deshake_opencl, erosion_opencl, dilation_opencl, nlmeans_opencl, overlay_opencl, pad_opencl, prewitt_opencl, remap_opencl, roberts_opencl, sobel_opencl, tonemap_opencl, unsharp_opencl, xfade_opencl

**VAAPI:**
- drawbox_vaapi, hstack_vaapi, overlay_vaapi, pad_vaapi, tonemap_vaapi, vstack_vaapi, xstack_vaapi

**Vulkan:**
- avgblur_vulkan, blackdetect_vulkan, blend_vulkan, bwdif_vulkan, chromaber_vulkan, color_vulkan, flip_vulkan, gblur_vulkan, hflip_vulkan, interlace_vulkan, nlmeans_vulkan, overlay_vulkan, transpose_vulkan, vflip_vulkan

**QSV (Intel QuickSync):**
- hstack_qsv, vstack_qsv, xstack_qsv

**NPP (NVIDIA Performance Primitives):**
- scale_npp, scale2ref_npp, sharpen_npp, transpose_npp

**VideoToolbox (macOS):**
- scale_vt, transpose_vt

**AMF (AMD):**
- sr_amf, vpp_amf

---

## 3. COMPLEX FILTERGRAPH SYNTAX

### 3.1 Basic Syntax
```
-filter_complex "[input_label]filter1=params[output_label];[label2]filter2[out2]"
```

### 3.2 Multiple Inputs/Outputs
```
# Overlay video1 on video0
-filter_complex "[0:v][1:v]overlay=x=10:y=10[out]"

# Multiple operations chained
-filter_complex "[0:v]scale=1280:720[scaled];[scaled][1:v]overlay[out]"

# Split and process
-filter_complex "[0:v]split=2[a][b];[a]hue=s=0[gray];[b][gray]hstack[out]"
```

### 3.3 Stream Selection
- `[0:v]` - Video stream from first input
- `[1:a]` - Audio stream from second input
- `[0:v:0]` - First video stream from first input
- `[label]` - Custom labeled stream

### 3.4 Multiple Filtergraphs
```
-filter_complex "[0:v]scale=1280:720[v];[0:a]volume=2.0[a]" -map "[v]" -map "[a]"
```

### 3.5 Complex Example
```
-filter_complex "
[0:v]scale=1920:1080,setsar=1[base];
[1:v]scale=320:240[pip];
[base][pip]overlay=x=W-w-10:y=10[vid];
[0:a][1:a]amix=inputs=2[aud]
" -map "[vid]" -map "[aud]"
```

---

## 4. STREAM SELECTION AND MAPPING

### 4.1 Map Syntax
```
-map input_file_index:stream_specifier
```

### 4.2 Stream Specifiers
- `0` - All streams from first input
- `0:0` - First stream from first input
- `0:v` - All video streams from first input
- `0:a` - All audio streams
- `0:s` - All subtitle streams
- `0:v:0` - First video stream
- `0:a:1` - Second audio stream
- `0:m:language:eng` - Streams with English language metadata

### 4.3 Examples
```
# Map all streams
-map 0

# Map specific streams
-map 0:v:0 -map 0:a:1

# Negative mapping (exclude)
-map 0 -map -0:a:1

# Optional mapping (don't fail if missing)
-map 0:v -map 0:a?

# Map from filtergraph
-map "[outv]" -map "[outa]"
```

### 4.4 Automatic Selection
- Video: highest resolution
- Audio: most channels
- Subtitles: first matching type

---

## 5. TIME-BASED OPERATIONS

### 5.1 Seeking (Input)
```
# Seek before input (fast, keyframe accurate)
-ss 00:01:30 -i input.mp4

# Seek with frame accuracy (slower, exact)
-i input.mp4 -ss 00:01:30 -accurate_seek

# Seek from end
-sseof -00:01:00 -i input.mp4
```

### 5.2 Duration Limiting
```
# Duration
-t 00:10:00         # 10 minutes duration
-to 00:15:00        # Stop at 15 minute mark

# Frame count
-frames:v 300       # 300 video frames
-vframes 300        # Same as above
```

### 5.3 Time Formats
- Seconds: `90.5`
- HH:MM:SS: `00:01:30.5`
- HH:MM:SS.ms: `00:01:30.500`

### 5.4 Trim Filter
```
# Trim video
-vf "trim=start=10:end=60"
-vf "trim=start_frame=300:end_frame=900"

# Audio trim
-af "atrim=start=10:end=60"
```

### 5.5 Looping
```
# Loop input
-stream_loop 3 -i input.mp4    # Loop 3 times (-1 = infinite)

# Loop filter
-vf "loop=loop=5:size=150"     # Loop 150 frames 5 times
```

---

## 6. VIDEO SCALING, PADDING, OVERLAY

### 6.1 Scaling
```
# Basic scaling
-vf "scale=1920:1080"

# Keep aspect ratio
-vf "scale=1920:-1"     # Auto-calculate height
-vf "scale=-1:1080"     # Auto-calculate width
-vf "scale='min(1920,iw)':'min(1080,ih)'"  # Don't upscale

# Scaling algorithms
-vf "scale=1920:1080:flags=lanczos"
# Flags: fast_bilinear, bilinear, bicubic, neighbor, area, bicublin, gauss, sinc, lanczos, spline

# Force divisible by 2 (codec requirement)
-vf "scale='trunc(iw/2)*2':'trunc(ih/2)*2'"

# Fit within box
-vf "scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease"
-vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
```

### 6.2 Padding
```
# Add black borders
-vf "pad=1920:1080:(ow-iw)/2:(oh-ih)/2"

# Colored padding
-vf "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=white"

# Aspect ratio padding
-vf "pad=ih*16/9:ih:(ow-iw)/2:0"
```

### 6.3 Overlay
```
# Basic overlay
-filter_complex "[0:v][1:v]overlay=x=10:y=10"

# Centered overlay
-filter_complex "[0:v][1:v]overlay=x=(W-w)/2:y=(H-h)/2"

# Bottom-right corner
-filter_complex "[0:v][1:v]overlay=x=W-w-10:y=H-h-10"

# Timed overlay (show from 5s to 15s)
-filter_complex "[0:v][1:v]overlay=x=10:y=10:enable='between(t,5,15)'"

# Multiple overlays
-filter_complex "[0:v][1:v]overlay=x=10:y=10[tmp];[tmp][2:v]overlay=x=W-w-10:y=10"

# Blend modes
-filter_complex "[0:v][1:v]overlay=x=10:y=10:format=rgb:eval=frame"
```

---

## 7. TEXT AND SUBTITLE BURNING

### 7.1 Drawtext Filter
```
# Simple text
-vf "drawtext=text='Hello World':x=10:y=10:fontsize=24:fontcolor=white"

# With shadow
-vf "drawtext=text='Title':x=(w-text_w)/2:y=50:fontsize=48:fontcolor=white:shadowcolor=black:shadowx=2:shadowy=2"

# From file
-vf "drawtext=textfile=subtitle.txt:x=10:y=10"

# Timecode
-vf "drawtext=text='%{pts\:hms}':x=10:y=10:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5"

# Frame number
-vf "drawtext=text='Frame\: %{n}':x=10:y=10"

# Metadata
-vf "drawtext=text='%{metadata\:lavf.format.filename}':x=10:y=10"

# Dynamic text (changes over time)
-vf "drawtext=text='Time\: %{pts\:hms}':x=10:y=10:fontsize=24:fontcolor=white:enable='gte(t,0)'"

# Multiple text overlays
-vf "drawtext=text='Top':x=(w-text_w)/2:y=10,drawtext=text='Bottom':x=(w-text_w)/2:y=h-th-10"

# Fade in/out
-vf "drawtext=text='Title':x=(w-text_w)/2:y=50:fontsize=48:alpha='if(lt(t,1),t,if(lt(t,9),1,(10-t)))'"
```

### 7.2 Subtitle Burning
```
# ASS/SSA subtitles
-vf "ass=subtitle.ass"

# SRT subtitles (converted to ASS)
-vf "subtitles=subtitle.srt"

# From MKV file
-vf "subtitles=video.mkv:si=0"

# Force style
-vf "subtitles=sub.srt:force_style='FontName=Arial,FontSize=24,PrimaryColour=&H00FFFF&'"

# Character encoding
-vf "subtitles=sub.srt:charenc=UTF-8"
```

### 7.3 Advanced Text Features
```
# Box around text
-vf "drawtext=text='Boxed':x=10:y=10:box=1:boxcolor=black@0.5:boxborderw=5"

# Outline
-vf "drawtext=text='Outlined':x=10:y=10:borderw=2:bordercolor=black"

# Font options
-vf "drawtext=text='Custom':fontfile=/path/to/font.ttf:fontsize=36:fontcolor=yellow"

# Text file with reloading
-vf "drawtext=textfile=dynamic.txt:reload=1:x=10:y=10"

# Scrolling text (from right to left)
-vf "drawtext=text='Scrolling Text':x=w-mod(t*100,w+tw):y=h-th-10:fontsize=24"

# Word wrap
-vf "drawtext=textfile=long.txt:x=10:y=10:fontsize=20:line_spacing=5:borderw=2"
```

---

## 8. ENCODING OPTIONS AND QUALITY SETTINGS

### 8.1 Video Encoders

**H.264 (libx264):**
```
# Constant Rate Factor (CRF) - Recommended
-c:v libx264 -crf 23                    # Default quality (0-51, lower = better)
-c:v libx264 -crf 18                    # High quality
-c:v libx264 -crf 28                    # Low quality

# Preset (speed vs compression)
-c:v libx264 -preset ultrafast          # Fastest, largest file
-c:v libx264 -preset veryfast
-c:v libx264 -preset faster
-c:v libx264 -preset fast
-c:v libx264 -preset medium             # Default
-c:v libx264 -preset slow               # Better compression
-c:v libx264 -preset slower
-c:v libx264 -preset veryslow           # Best compression
-c:v libx264 -preset placebo            # Diminishing returns

# Profile and level
-c:v libx264 -profile:v high -level 4.1

# Tune options
-c:v libx264 -tune film                 # For film content
-c:v libx264 -tune animation            # For animation
-c:v libx264 -tune grain                # For grainy content
-c:v libx264 -tune stillimage           # For slideshow
-c:v libx264 -tune fastdecode           # For fast decoding
-c:v libx264 -tune zerolatency          # For streaming

# Bitrate modes
-c:v libx264 -b:v 2M                    # Constant bitrate
-c:v libx264 -b:v 2M -maxrate 2.5M -bufsize 5M  # Constrained VBR
-c:v libx264 -crf 23 -maxrate 2M -bufsize 4M    # CRF with max bitrate

# Two-pass encoding
# Pass 1:
-c:v libx264 -b:v 2M -pass 1 -f null /dev/null
# Pass 2:
-c:v libx264 -b:v 2M -pass 2 output.mp4

# Advanced options
-c:v libx264 -crf 20 -g 60 -bf 2 -refs 4 -me_method umh -subq 8
```

**H.265/HEVC (libx265):**
```
-c:v libx265 -crf 28 -preset medium
-c:v libx265 -x265-params "crf=25:qcomp=0.8:aq-mode=1:aq-strength=1.0:qg-size=16:psy-rd=0.7:psy-rdoq=5.0:rdoq-level=1"
```

**VP9 (libvpx-vp9):**
```
# Single pass CRF
-c:v libvpx-vp9 -crf 31 -b:v 0

# Two-pass
# Pass 1:
-c:v libvpx-vp9 -b:v 2M -pass 1 -f null /dev/null
# Pass 2:
-c:v libvpx-vp9 -b:v 2M -pass 2 output.webm

# Quality settings
-c:v libvpx-vp9 -crf 31 -b:v 0 -quality good -cpu-used 0   # Slowest, best
-c:v libvpx-vp9 -crf 31 -b:v 0 -quality good -cpu-used 4   # Balanced
```

**AV1 (libaom-av1, libsvtav1):**
```
# libaom-av1
-c:v libaom-av1 -crf 30 -b:v 0 -cpu-used 4

# libsvtav1 (faster)
-c:v libsvtav1 -crf 35 -preset 8
```

**ProRes:**
```
-c:v prores_ks -profile:v 3             # ProRes HQ
-c:v prores_ks -profile:v 2             # ProRes Standard
# Profiles: 0=Proxy, 1=LT, 2=Standard, 3=HQ, 4=4444, 5=4444XQ
```

**Hardware Encoders:**
```
# NVIDIA NVENC (H.264)
-c:v h264_nvenc -preset p7 -tune hq -rc vbr -cq 19 -b:v 5M -maxrate 10M

# NVIDIA NVENC (HEVC)
-c:v hevc_nvenc -preset p7 -tune hq -rc vbr -cq 21 -b:v 4M

# Intel QuickSync (H.264)
-c:v h264_qsv -preset veryslow -global_quality 23

# AMD AMF
-c:v h264_amf -quality quality -rc cqp -qp_i 23 -qp_p 23

# Apple VideoToolbox (macOS)
-c:v h264_videotoolbox -b:v 5M

# VAAPI (Linux)
-c:v h264_vaapi -qp 23
```

### 8.2 Audio Encoders

**AAC:**
```
-c:a aac -b:a 192k                      # Bitrate
-c:a aac -q:a 2                         # VBR quality (0.1-2, lower=better)
```

**Opus:**
```
-c:a libopus -b:a 128k
-c:a libopus -vbr on -compression_level 10 -b:a 128k
```

**MP3:**
```
-c:a libmp3lame -b:a 192k
-c:a libmp3lame -q:a 2                  # VBR (0-9, lower=better)
```

**AC3:**
```
-c:a ac3 -b:a 448k
```

**FLAC (lossless):**
```
-c:a flac -compression_level 8
```

**PCM (uncompressed):**
```
-c:a pcm_s16le                          # 16-bit PCM
-c:a pcm_s24le                          # 24-bit PCM
```

### 8.3 Pixel Formats
```
-pix_fmt yuv420p                        # Most compatible
-pix_fmt yuv422p                        # Professional (10-bit)
-pix_fmt yuv444p                        # No chroma subsampling
-pix_fmt rgb24                          # RGB
-pix_fmt rgba                           # RGB with alpha
```

### 8.4 Frame Rate Control
```
-r 30                                   # Force output frame rate
-r 24 -i input.mp4 -r 30 output.mp4    # Input and output rates
-fpsmax 60                              # Maximum frame rate
```

---

## 9. CONTAINER FORMATS

### 9.1 Major Formats

**MP4 (MPEG-4 Part 14):**
```
-f mp4
# Codecs: H.264, H.265, MPEG-4, AAC, MP3, AC3
# Use: Web, streaming, general purpose
# Options:
-movflags +faststart                    # Enable progressive download
-movflags +frag_keyframe+empty_moov     # Fragmented MP4 for streaming
```

**MOV (QuickTime):**
```
-f mov
# Similar to MP4, Apple ecosystem
-c:v prores_ks -c:a pcm_s24le          # Professional editing
```

**MKV (Matroska):**
```
-f matroska
# Universal container, supports almost any codec
# Can store multiple audio/subtitle tracks
# Supports chapters, attachments
```

**WebM:**
```
-f webm
# Web-optimized
# Codecs: VP8, VP9, AV1, Opus, Vorbis
```

**AVI:**
```
-f avi
# Legacy format
# Limited codec support
```

**MPEG-TS (Transport Stream):**
```
-f mpegts
# Broadcasting, streaming
-mpegts_flags +resend_headers
```

**HLS (HTTP Live Streaming):**
```
-f hls
-hls_time 6                             # Segment duration
-hls_list_size 0                        # Keep all segments in playlist
-hls_segment_filename 'segment%03d.ts'
```

**DASH:**
```
-f dash
-seg_duration 4
-use_template 1 -use_timeline 1
```

### 9.2 Format-Specific Options

**MP4 Fast Start:**
```
-movflags +faststart                    # Move moov atom to beginning
```

**Fragmented MP4:**
```
-movflags +frag_keyframe+empty_moov+default_base_moof
```

**Matroska Options:**
```
-reserve_index_space 50000              # Reserve space for cues
-default_mode infer_no_subs             # Don't mark streams as default
```

---

## 10. HARDWARE ACCELERATION

### 10.1 NVIDIA CUDA
```
# Initialization
-hwaccel cuda -hwaccel_output_format cuda

# Full CUDA pipeline
-hwaccel cuda -hwaccel_output_format cuda -i input.mp4 \
-vf "scale_cuda=1920:1080,hwdownload,format=nv12" \
-c:v h264_nvenc output.mp4

# Filters: scale_cuda, overlay_cuda, chromakey_cuda, yadif_cuda, etc.
```

### 10.2 Intel QuickSync (QSV)
```
# Initialization
-hwaccel qsv -c:v h264_qsv

# Encoding
-c:v h264_qsv -preset veryslow -global_quality 23

# Full pipeline
-hwaccel qsv -c:v h264_qsv -i input.mp4 \
-vf "scale_qsv=1920:1080" \
-c:v h264_qsv output.mp4

# Filters: scale_qsv, hstack_qsv, vstack_qsv, xstack_qsv
```

### 10.3 AMD AMF
```
-c:v h264_amf -quality quality -rc cqp -qp_i 23

# Filters: vpp_amf, sr_amf
```

### 10.4 VAAPI (Linux)
```
# Initialization
-hwaccel vaapi -hwaccel_device /dev/dri/renderD128 \
-hwaccel_output_format vaapi

# Encoding
-vf "scale_vaapi=1920:1080" -c:v h264_vaapi -qp 23

# Filters: scale_vaapi, overlay_vaapi, tonemap_vaapi, drawbox_vaapi, etc.
```

### 10.5 VideoToolbox (macOS)
```
-hwaccel videotoolbox

# Encoding
-c:v h264_videotoolbox -b:v 5M

# Filters: scale_vt, transpose_vt
```

### 10.6 Vulkan
```
-init_hw_device vulkan

# Filters: avgblur_vulkan, blend_vulkan, bwdif_vulkan, chromaber_vulkan,
# gblur_vulkan, overlay_vulkan, scale_vulkan, etc.
```

### 10.7 OpenCL
```
-init_hw_device opencl

# Filters: avgblur_opencl, boxblur_opencl, convolution_opencl,
# deshake_opencl, nlmeans_opencl, overlay_opencl, etc.
```

---

## 11. MULTI-INPUT HANDLING AND CONCATENATION

### 11.1 Multiple Input Files
```
# Two inputs
ffmpeg -i video1.mp4 -i video2.mp4 ...

# Reference by index
-map 0:v                                # First input video
-map 1:a                                # Second input audio
```

### 11.2 Concat Demuxer
```
# Create file list (concat.txt):
file 'video1.mp4'
file 'video2.mp4'
file 'video3.mp4'

# Concatenate
ffmpeg -f concat -safe 0 -i concat.txt -c copy output.mp4
```

### 11.3 Concat Filter
```
# Same resolution/codec
-filter_complex "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[outv][outa]" \
-map "[outv]" -map "[outa]"

# Different resolutions (scale first)
-filter_complex "
[0:v]scale=1920:1080,setsar=1[v0];
[1:v]scale=1920:1080,setsar=1[v1];
[v0][0:a][v1][1:a]concat=n=2:v=1:a=1[outv][outa]
"
```

### 11.4 Concat Protocol
```
ffmpeg -i "concat:file1.ts|file2.ts|file3.ts" -c copy output.ts
```

### 11.5 Complex Multi-Input Example
```
# Picture-in-picture with background music
ffmpeg -i main.mp4 -i pip.mp4 -i music.mp3 \
-filter_complex "
[0:v][1:v]overlay=x=W-w-10:y=10[video];
[0:a][2:a]amix=inputs=2:duration=first[audio]
" \
-map "[video]" -map "[audio]" output.mp4
```

---

## 12. ADVANCED PROFESSIONAL FEATURES

### 12.1 Timecode & Metadata
```
# Embed timecode
-metadata timecode="01:00:00:00"

# Title, artist, etc.
-metadata title="My Video" -metadata author="Name"

# Per-stream metadata
-metadata:s:a:0 language=eng
-metadata:s:s:0 language=fra

# Copy all metadata
-map_metadata 0

# Remove metadata
-map_metadata -1
```

### 12.2 Color Management
```
# Set colorspace
-colorspace bt709
-color_primaries bt709
-color_trc bt709
-color_range tv                         # or 'pc' for full range

# HDR metadata
-color_primaries bt2020
-color_trc smpte2084                    # PQ
-colorspace bt2020nc
-color_range tv

# Master display
-master_display "G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)"

# Max CLL
-max_cll "1000,400"
```

### 12.3 Audio Channel Mapping
```
# Stereo to 5.1
-af "pan=5.1|FL=FL|FR=FR|FC=0.5*FL+0.5*FR|LFE=0|BL=FL|BR=FR"

# Extract center channel
-af "pan=mono|c0=FC"

# Swap left and right
-af "channelmap=1-0|0-1"
```

### 12.4 Batch Processing
```
# Process all MP4 files
for f in *.mp4; do
    ffmpeg -i "$f" -c:v libx264 -crf 23 "encoded/${f%.mp4}_h264.mp4"
done
```

### 12.5 Progress Monitoring
```
-progress pipe:1                        # Output progress to stdout
-stats_period 1                         # Update every second
```

### 12.6 Quality Control
```
# Constant quality
-crf 23                                 # CRF mode

# Constrained quality
-crf 23 -maxrate 2M -bufsize 4M

# Bitrate control
-b:v 2M -minrate 1.5M -maxrate 2.5M -bufsize 5M

# Two-pass for precise bitrate
-pass 1 / -pass 2
```

### 12.7 Advanced Filtergraph Features
```
# Split and process differently
-filter_complex "
[0:v]split=3[original][denoised_input][scaled_input];
[denoised_input]hqdn3d[denoised];
[scaled_input]scale=1280:720[scaled];
[original][denoised][scaled]xstack=inputs=3:layout=0_0|w0_0|w0+w1_0[out]
"

# Conditional processing
-filter_complex "[0:v]eq=brightness=0.06:enable='between(t,10,20)'[out]"

# Frame-accurate operations
-filter_complex "[0:v]trim=start_frame=100:end_frame=200,setpts=PTS-STARTPTS[out]"
```

### 12.8 Streaming
```
# RTMP
ffmpeg -re -i input.mp4 -c:v libx264 -preset veryfast -b:v 3M \
-c:a aac -b:a 128k -f flv rtmp://server/live/stream

# HLS
ffmpeg -i input.mp4 -c:v libx264 -c:a aac -f hls \
-hls_time 6 -hls_list_size 0 -hls_segment_filename 'segment%03d.ts' \
playlist.m3u8

# UDP
ffmpeg -re -i input.mp4 -c copy -f mpegts udp://192.168.1.100:1234
```

### 12.9 Image Sequences
```
# Input image sequence
-framerate 24 -i frame_%04d.png

# Output image sequence  
-start_number 1 frame_%04d.png

# From video to images
-i video.mp4 -vf fps=1 frame_%04d.png   # 1 frame per second
```

### 12.10 Debugging & Analysis
```
-loglevel debug                         # Verbose logging
-report                                 # Generate detailed report
-benchmark                              # Show timing info
-vstats_file stats.log                  # Video statistics
-debug_ts                               # Timestamp debugging
```

### 12.11 Performance Optimization
```
-threads 8                              # Number of threads
-filter_threads 4                       # Filter thread count
-preset ultrafast                       # Fast encoding
-tune zerolatency                       # Low latency
```

### 12.12 Chapter Markers
```
# Add chapters from metadata file
-i input.mp4 -i chapters.txt -map_metadata 1 -c copy output.mp4

# chapters.txt format:
# ;FFMETADATA1
# [CHAPTER]
# TIMEBASE=1/1000
# START=0
# END=30000
# title=Chapter 1
```

### 12.13 Closed Captions
```
# Extract EIA-608 captions
-vf "readeia608" -f data -map 0:v:cc output.txt

# Burn in captions
-vf "subtitles=captions.srt"
```

### 12.14 Advanced Audio Features
```
# Loudness normalization (EBU R128)
-af "loudnorm=I=-16:TP=-1.5:LRA=11"

# Two-pass loudness
# Pass 1:
ffmpeg -i input.mp3 -af loudnorm=print_format=json -f null -
# Use output values in Pass 2

# Audio ducking
-filter_complex "[0:a][1:a]sidechaincompress=threshold=0.1:ratio=4:attack=5:release=50[out]"

# Noise gate
-af "agate=threshold=0.03:ratio=2:attack=5:release=50"
```

### 12.15 Video Quality Metrics
```
# PSNR
-filter_complex "[0:v][1:v]psnr=stats_file=psnr.log[out]"

# SSIM
-filter_complex "[0:v][1:v]ssim=stats_file=ssim.log[out]"

# VMAF
-filter_complex "[0:v][1:v]libvmaf=log_path=vmaf.xml:model_path=/path/to/model[out]"
```

---

## FILTER PARAMETER DETAILS

### Key Video Filter Parameters

**scale:**
- width, height: Output dimensions or -1 for auto, -2 for auto-even
- flags: Scaling algorithm (lanczos, bicubic, etc.)
- force_original_aspect_ratio: decrease, increase

**overlay:**
- x, y: Position (supports expressions like W-w, H-h)
- eof_action: Action at end (repeat, endall, pass)
- format: Pixel format (yuv420, rgb, etc.)
- enable: Enable expression

**drawtext:**
- text: Text string
- textfile: Text from file
- x, y: Position (supports expressions)
- fontsize, fontcolor, fontfile
- box, boxcolor, boxborderw
- shadowcolor, shadowx, shadowy
- enable: Enable expression

**crop:**
- w, h: Width, height
- x, y: Top-left position
- keep_aspect: Keep aspect ratio

**pad:**
- width, height: Output size
- x, y: Input position
- color: Padding color

---

## COMMON USE CASE EXAMPLES

### Professional Edit Workflow
```
# High-quality intermediate (ProRes)
ffmpeg -i source.mov -c:v prores_ks -profile:v 3 -c:a pcm_s24le intermediate.mov

# Final delivery (H.264)
ffmpeg -i intermediate.mov -c:v libx264 -preset slow -crf 18 \
-pix_fmt yuv420p -c:a aac -b:a 192k final.mp4
```

### Multi-camera Edit
```
ffmpeg -i cam1.mp4 -i cam2.mp4 -i cam3.mp4 -filter_complex "
[0:v]scale=1920:1080[v0];
[1:v]scale=960:540[v1];
[2:v]scale=960:540[v2];
[v0][v1]overlay=x=W-w:y=0[tmp];
[tmp][v2]overlay=x=W-w:y=H-h[out]
" -map "[out]" output.mp4
```

### Live Stream Re-encoding
```
ffmpeg -re -i input.mp4 -c:v libx264 -preset veryfast -tune zerolatency \
-b:v 3M -maxrate 3M -bufsize 6M -pix_fmt yuv420p -g 60 -c:a aac \
-b:a 128k -ar 44100 -f flv rtmp://server/app/stream
```

---

**END OF COMPREHENSIVE FFMPEG DOCUMENTATION ANALYSIS**
