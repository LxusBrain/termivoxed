# COMPREHENSIVE FFMPEG CODEC REFERENCE
## Professional Video Export Guide for TermiVoxed Video Editor

**Source:** `/Users/santhu/Downloads/SubsGen2/console_video_editor/web_ui/documentation/ffmpeg/ffmpeg-codec`
**Generated:** 2025-12-14
**Total Lines Analyzed:** 5,071

---

## TABLE OF CONTENTS

1. [Video Codecs Overview](#video-codecs-overview)
2. [Audio Codecs Overview](#audio-codecs-overview)
3. [Hardware Acceleration Encoders](#hardware-acceleration-encoders)
4. [Quality Settings & Rate Control](#quality-settings--rate-control)
5. [Codec Compatibility Matrix](#codec-compatibility-matrix)
6. [Lossless vs Lossy Options](#lossless-vs-lossy-options)
7. [Best Practices by Output Format](#best-practices-by-output-format)
8. [Complete Codec Details](#complete-codec-details)

---

## 1. VIDEO CODECS OVERVIEW

### Modern/Recommended Codecs

#### **AV1 (AOMedia Video 1)**
- **Encoders:** `av1` (native), `libdav1d` (decoder), `libaom-av1`, `librav1e`, `libsvtav1`
- **Best For:** Maximum compression efficiency, future-proof streaming
- **Quality Range:** CRF 0-63 (lower = better quality)
- **Hardware Support:** `av1_qsv` (Intel QuickSync), `av1_vaapi` (VAAPI), `av1_mf` (MediaFoundation)

**libaom-av1 Key Options:**
- `cpu-used`: 0-8 (speed/quality tradeoff, 0=slowest/best, 8=fastest/worst)
- `crf`: 0-63 (constant quality mode)
- `b`: bitrate target in bits/s
- `tune`: psnr, ssim
- `aq-mode`: none(0), variance(1), complexity(2), cyclic(3)
- `enable-cdef`: Constrained Directional Enhancement Filter (default: true)
- `enable-restoration`: Loop Restoration Filter (default: true)
- `row-mt`: Enable row-based multi-threading

**librav1e Options:**
- `speed`: 0-10 (preset speed)
- `qp`: 0-255 (quantizer mode)
- `tiles`: number of tiles for parallel encoding

**libsvtav1 Options:**
- `preset`: 0-13 (higher = faster but lower quality)
- `crf`: 0-63 (constant rate factor)
- `qp`: 0-63 (quantization parameter)
- `sc_detection`: Enable scene change detection
- `la_depth`: 0-120 (look-ahead depth)
- `tile_rows`: 0-6 (log2 of tile rows)
- `tile_columns`: 0-4 (log2 of tile columns)

#### **HEVC/H.265**
- **Encoders:** `hevc` (native), `libx265`, `libkvazaar`, `libvvenc`
- **Best For:** 4K/8K content, high-quality archival with smaller file sizes than H.264
- **Decoder Options:** MV-HEVC multiview support (up to 2 views)

**libx265 Key Options:**
- `preset`: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow, placebo
- `tune`: psnr, ssim, grain, zerolatency, fastdecode
- `crf`: 0-51 (0=lossless, 23=default, 51=worst)
- `qp`: 0-51 (constant QP mode)
- `profile`: main, main10, main12, main444-8, main444-10
- `x265-params`: Advanced options as key=value pairs

**libkvazaar Options:**
- `b`: Target video bitrate (enables rate control)
- `kvazaar-params`: Parameters as name=value pairs

**libvvenc (H.266/VVC):**
- `preset`: quality/encoding speed tradeoff
- `qp`: constant quantization parameter
- `bitdepth8`: Use 8-bit instead of 10-bit (default: off)
- `period`: Intra refresh period in seconds
- `vvenc-params`: Advanced options

#### **H.264/AVC**
- **Encoders:** `libx264`, `libx264rgb`, `libopenh264`
- **Best For:** Maximum compatibility, web streaming, broadcast
- **Color Spaces:** libx264 (YUV), libx264rgb (RGB)

**libx264 Comprehensive Options:**

*Rate Control:*
- `crf`: 0-51 (18=visually lossless, 23=default, 28=acceptable quality)
- `crf_max`: Maximum CRF in VBR mode
- `qp`: 0-51 (constant QP mode)
- `b`: Target bitrate in bits/s
- `minrate/maxrate`: Min/max bitrate for VBR

*Presets (Speed/Quality):*
- `ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow, placebo`

*Tuning:*
- `film`: Live-action content
- `animation`: Hand-drawn animation
- `grain`: Preserves film grain
- `stillimage`: Slideshow-like content
- `psnr/ssim`: Metric optimization
- `fastdecode`: Faster decoding
- `zerolatency`: Low-latency streaming

*Profiles:*
- `baseline`: Maximum compatibility, no B-frames
- `main`: Standard compatibility
- `high`: Best compression (8x8 DCT)
- `high10`: 10-bit color depth
- `high422`: 4:2:2 chroma subsampling
- `high444`: 4:4:4 (no chroma subsampling)

*Advanced Options:*
- `refs`: 0-16 (reference frames)
- `me_method`: dia, hex, umh, esa, tesa (motion estimation)
- `subq`: 0-11 (sub-pixel motion estimation quality)
- `trellis`: 0-2 (rate-distortion optimization)
- `aq-mode`: 0=off, 1=variance, 2=auto-variance
- `aq-strength`: 0.0-2.0 (adaptive quantization)
- `psy-rd`: Psychovisual optimization (psy-rd:psy-trellis)
- `rc-lookahead`: 0-250 (frames for rate control lookahead)
- `weightb`: Weighted prediction for B-frames
- `weightp`: 0=off, 1=simple, 2=smart (P-frame weighted prediction)
- `b-pyramid`: none, strict, normal (B-frame pyramid)
- `direct-pred`: none, spatial, temporal, auto
- `deblock`: alpha:beta (loop filter)
- `partitions`: p8x8,p4x4,b8x8,i8x8,i4x4 (macroblock partitions)
- `8x8dct`: Enable 8x8 DCT (high profile)
- `cabac`: Enable CABAC entropy coding
- `nal-hrd`: none, vbr, cbr (HRD signaling)

**libopenh264 Options:**
- `b`: Bitrate in bits/s
- `g`: GOP size
- `maxrate`: Maximum bitrate
- `slices`: Number of slices (parallelization)
- `loopfilter`: Enable/disable loop filter
- `profile`: main (enables CABAC)
- `max_nal_size`: Maximum NAL size in bytes
- `allow_skip_frames`: Skip frames to hit target bitrate

#### **VP9**
- **Encoder:** `libvpx` (VP9 mode)
- **Best For:** WebM containers, YouTube, royalty-free alternative to HEVC
- **Lossless Mode:** Supported via `lossless` option

**libvpx VP9-Specific Options:**
- `lossless`: Enable lossless mode
- `tile-columns/tile-rows`: Parallel encoding tiles (log2 values)
- `frame-parallel`: Enable frame parallel decodability
- `aq-mode`: 0=off, 1=variance, 2=complexity, 3=cyclic refresh, 4=equator360
- `row-mt`: Row-based multi-threading
- `tune-content`: default(0), screen(1), film(2)
- `enable-tpl`: Temporal dependency model
- `corpus-complexity`: 0-10000 (VBR mode variant)

**Common VP8/VP9 Options:**
- `b`: Target bitrate in bits/s
- `crf`: 0-63 (constant quality, VP9), 4-63 (VP8)
- `quality/deadline`: best, good, realtime
- `cpu-used`: Speed preset (higher = faster/lower quality)
- `auto-alt-ref`: Alternate reference frames (2-pass, VP9: multi-layer with values >1)
- `lag-in-frames`: Lookahead frames
- `error-resilient`: Enable error resilience features

#### **VP8**
- **Encoder:** `libvpx` (VP8 mode)
- **Best For:** WebM, older browser compatibility
- **Screen Content:** `screen-content-mode`: 0=off, 1=screen, 2=aggressive RC

### Specialized/Professional Codecs

#### **ProRes (Apple)**
- **Encoders:** `prores-aw`, `prores-ks`
- **Profiles:**
  - `proxy`: Lowest quality, offline editing
  - `lt`: Light, lower bitrate
  - `standard`: Standard quality (default)
  - `hq`: High Quality, 10-bit
  - `4444`: 4:4:4:4 with alpha
  - `4444xq`: Highest quality with alpha

**prores-ks Options:**
- `profile`: proxy, lt, standard, hq, 4444, 4444xq
- `quant_mat`: auto, default, proxy, lt, standard, hq
- `bits_per_mb`: 200-8000 (bits per macroblock)
- `mbs_per_slice`: 1-8 (macroblocks per slice, default: 8)
- `vendor`: 4-byte vendor ID (e.g., 'apl0' for Apple)
- `alpha_bits`: 0, 8, 16 (alpha channel bit depth)

#### **DNxHD/DNxHR (Avid)**
- **Best For:** Professional editing, broadcast delivery
- **Profiles:** DNxHD (HD), DNxHR (4K/UHD)

#### **JPEG2000**
- **Best For:** Digital cinema (DCP), archival
- **Lossless Option:** `-pred 1` (dwt53)

**JPEG2000 Options:**
- `format`: j2k, jp2 (allows non-RGB formats)
- `tile_width/tile_height`: 1-1073741824 (default: 256)
- `pred`: dwt97int (lossy, default), dwt53 (lossless)
- `sop`: Add SOP marker at packet start
- `eph`: Add EPH marker at packet header end
- `prog`: lrcp, rlcp, rpcl, pcrl, cprl (progression order, default: lrcp)
- `layer_rates`: Compression ratios per layer (e.g., "100,10,1")

#### **FFV1 (Lossless)**
- **Best For:** Archival, lossless compression
- **Container:** Recommended with MKV/AVI

**FFV1 Options:**
- `context`: 0=small (default), 1=big
- `coder`: rice (Golomb rice), range_def (range coder default), range_tab (range coder custom)
- `slicecrc`: -1=auto, 1=crc with zero state, 2=crc with non-zero state
- `qtable`: default, 8bit, greater8bit

#### **JPEG XL (libjxl)**
- **Best For:** Next-gen image/video codec, excellent compression
- **Lossless:** distance=0.0

**libjxl Options:**
- `distance`: 0.0-15.0 (quality, 0.0=lossless, 1.0≈JPEG Q90)
- `effort`: 1-9 (encoding effort, default: 7)
- `modular`: Force Modular mode (auto uses VarDCT for lossy)

### Legacy/Special Purpose Codecs

#### **MPEG-2**
- **Encoder:** `mpeg2`
- **Best For:** DVD authoring, broadcast (legacy)

**MPEG-2 Options:**
- `profile`: 422, high, ss (Spatially Scalable), snr (SNR Scalable), main, simple
- `level`: high, high1440, main, low
- `seq_disp_ext`: -1=auto, 0=never, 1=always
- `video_format`: unspecified, component, pal, ntsc, secam, mac
- `a53cc`: Import closed captions (default: 1)

#### **Theora (libtheora)**
- **Best For:** Open-source OGG containers
- **Rate Control:** CBR and VBR modes

**libtheora Options:**
- `b`: Video bitrate for CBR mode
- `flags`: Use +qscale for VBR mode
- `g`: GOP size
- `q`: 0-10 (VBR quality, multiplied by 6.3 for native range 0-63)

#### **Xvid (libxvid)**
- **Best For:** MPEG-4 Part 2 compatibility
- **Motion Estimation:** 6 quality levels (0-6)

**libxvid Options:**
- `me_quality`: 0=none, 1-2=basic, 3-4=advanced, 5-6=extended search
- `mbd`: simple, bits, rd (macroblock decision algorithm)
- `lumi_aq`: Lumi masking adaptive quantization
- `variance_aq`: Variance adaptive quantization
- `gmc`: Global motion compensation
- `ssim`: off, avg, frame (SSIM calculation)
- `ssim_acc`: 0-4 (SSIM accuracy vs speed)

#### **Cinepak (CVID)**
- **Best For:** Vintage compatibility (Windows 3.1, MacOS)
- **Quality:** `-q:v` 1-1000 (lower = better)

#### **GIF**
- **Best For:** Animations, web graphics

**GIF Options:**
- `gifflags`: offsetting, transdiff
- `gifimage`: Encode full GIF per frame vs animation
- `global_palette`: Write global palette (default: 1)

#### **Hap (Vidvox)**
- **Best For:** Real-time playback, VJ software

**Hap Options:**
- `format`: hap, hap_alpha, hap_q
- `chunks`: 1-64 (multithreaded decoding)
- `compressor`: none, snappy (default)

### Container-Specific Codecs

#### **WebP (libwebp)**
- **Modes:** Lossy (VP8-based), Lossless
- **Alpha Support:** Both modes

**libwebp Options:**
- `lossless`: 0=lossy (default), 1=lossless
- `compression_level`: 0-6 (higher = better/slower)
- `quality`: 0-100 (lossy: quality, lossless: effort)
- `preset`: none, default, picture, photo, drawing, icon, text

#### **PNG**
- **Encoder:** `png`
- **Lossless:** Always

**PNG Options:**
- `compression_level`: 0-9 (default: 9)
- `dpi/dpm`: Physical density
- `pred`: none, sub, up, avg, paeth, mixed (prediction method, default: paeth)

#### **MJPEG**
- **Best For:** Quick editing, screen recording

**MJPEG Options:**
- `huffman`: default, optimal

### Experimental/Research Codecs

#### **SNOW**
- **Best For:** Research, wavelet-based compression

**Options:**
- `iterative_dia_size`: Diamond size for iterative motion estimation

#### **VC2 (SMPTE/BBC Dirac Pro)**
- **Best For:** Professional broadcasting, low overhead

**VC2 Options:**
- `b`: Target bitrate (~1:6 of uncompressed for lossy)
- `field_order`: tt (top first), bb (bottom first) for interlaced
- `wavelet_depth`: 1-5 (default: 5, lower values = less compression)
- `wavelet_type`: 5_3 (LeGall), 9_7 (Deslauriers-Dubuc, default)
- `slice_width/slice_height`: Slice dimensions
- `tolerance`: Rate control undershoot tolerance (%)
- `qm`: default, flat, color (quantization matrix preset)

#### **VBN (Vizrt Binary Image)**
- **Best For:** Broadcast texture streaming

**Options:**
- `format`: dxt1, dxt5 (default), raw

---

## 2. AUDIO CODECS OVERVIEW

### Modern/Recommended Codecs

#### **AAC (Advanced Audio Coding)**
- **Encoders:** `aac` (native), `libfdk_aac` (external, higher quality)
- **Best For:** General purpose, streaming, mobile
- **Bitrate:** 64-320 kbps (per channel)

**Native AAC Encoder Options:**
- `b`: Bitrate in bits/s (default: 128k) - activates CBR mode
- `q` / `global_quality`: Variable bitrate mode quality
- `cutoff`: Cutoff frequency (auto if unspecified)
- `aac_coder`: twoloop (default), anmr (experimental), fast
- `aac_ms`: auto (default), enable, disable (mid/side coding)
- `aac_is`: auto (default), disable (intensity stereo)
- `aac_pns`: auto (default), disable (perceptual noise substitution)
- `aac_tns`: auto (default), disable (temporal noise shaping)
- `aac_ltp`: Long term prediction (low bandwidth)
- `profile`: aac_low (default), mpeg2_aac_low, aac_ltp

**libfdk_aac (External - Highest Quality):**
- `b`: Target bitrate
- `cutoff`: Cutoff frequency (default: 0 = auto)
- `profile`: aac_low, aac_he, aac_he_v2, aac_ld, aac_eld
- `afterburner`: 0/1 (quality improvement, default: 1)
- `eld_sbr`: 0/1 (SBR for ELD, default: 0)
- `eld_v2`: 0/1 (LD-MPS for ELD stereo, default: 0)
- `signaling`: default, implicit, explicit_sbr, explicit_hierarchical
- `latm`: 0/1 (LATM/LOAS encapsulation, default: 0)
- `header_period`: StreamMuxConfig repetition period
- `vbr`: 0=CBR, 1-5 (VBR quality, 5=highest)
  - VBR 1: ~32 kbps/ch
  - VBR 2: ~40 kbps/ch
  - VBR 3: ~48-56 kbps/ch
  - VBR 4: ~64 kbps/ch
  - VBR 5: ~80-96 kbps/ch

#### **Opus (libopus)**
- **Best For:** VoIP, low-latency streaming, podcasts
- **Bitrate:** 6-510 kbps
- **Latency:** 2.5-60ms frame duration

**libopus Options:**
- `b`: Bitrate in bits/s (FFmpeg) vs kbps (opusenc)
- `vbr`: off (hard-cbr), on (vbr, default), constrained (cvbr)
- `compression_level`: 0-10 (0=fastest, 10=highest quality, default: 10)
- `frame_duration`: 2.5, 5, 10, 20 (default), 40, 60 ms
- `packet_loss`: 0-100% (expected packet loss, default: 0)
- `fec`: Enable forward error correction (requires packet_loss > 0)
- `application`: voip, audio (default), lowdelay
- `cutoff`: 4000, 6000, 8000, 12000, 20000 Hz
- `mapping_family`: -1 (auto), 0 (mono/stereo), 1 (surround), 255 (independent)
- `apply_phase_inv`: 0/1 (phase inversion for intensity stereo, default: 1)

#### **FLAC (Lossless)**
- **Encoder:** `flac`
- **Best For:** Lossless archival, music preservation
- **Compression:** Level 0-12 (5=default)

**FLAC Options:**
- `compression_level`: 0-12 (5=default)
- `frame_size`: Samples per channel
- `lpc_coeff_precision`: 1-15 (default: 15)
- `lpc_type`: none, fixed, levinson, cholesky
- `lpc_passes`: Number of Cholesky factorization passes
- `min_partition_order`: Minimum partition order
- `max_partition_order`: Maximum partition order
- `prediction_order_method`: estimation, 2level, 4level, 8level, search, log
- `ch_mode`: auto, indep, left_side, right_side, mid_side
- `exact_rice_parameters`: 0/1 (exact calculation, slower)
- `multi_dim_quant`: 0/1 (2nd stage LPC, slower)

#### **AC-3/Dolby Digital (ac3, ac3_fixed)**
- **Best For:** DVD, broadcast, surround sound
- **Channels:** Up to 5.1
- **Bitrate:** 32-640 kbps

**AC-3 Options:**

*Rate Control:*
- `b`: Bitrate in bits/s
- `cutoff`: Lowpass cutoff frequency

*Metadata:*
- `per_frame_metadata`: 0=fixed (default), 1=dynamic
- `center_mixlev`: 0.707, 0.595 (default), 0.500 (downmix gain)
- `surround_mixlev`: 0.707, 0.500 (default), 0.000
- `mixing_level`: 80-111 or -1 (SPL in dB)
- `room_type`: 0=notindicated, 1=large, 2=small
- `copyright`: 0=off (default), 1=on
- `dialnorm`: -31 to -1 (dialogue normalization, default: -31)
- `dsur_mode`: 0=notindicated, 1=off, 2=on (Dolby Surround)
- `original`: 0=not original, 1=original (default)

*Extended Bitstream:*
- `dmix_mode`: 0=notindicated, 1=ltrt, 2=loro (downmix preference)
- `ltrt_cmixlev`: Lt/Rt center mix level (1.414 to 0.000)
- `ltrt_surmixlev`: Lt/Rt surround mix level (0.841 to 0.000)
- `loro_cmixlev`: Lo/Ro center mix level (1.414 to 0.000)
- `loro_surmixlev`: Lo/Ro surround mix level (0.841 to 0.000)
- `dsurex_mode`: 0=notindicated, 1=on, 2=off (Dolby Surround EX)
- `dheadphone_mode`: 0=notindicated, 1=on, 2=off (Dolby Headphone)
- `ad_conv_type`: 0=standard, 1=hdcd (A/D converter type)

*Other:*
- `stereo_rematrixing`: 0/1 (default: 1)
- `channel_coupling`: -1=auto, 0=off, 1=on (floating-point only, default: auto)
- `cpl_start_band`: 1-15 or -1=auto (coupling start band)

### Lossy Codecs

#### **MP3 (libmp3lame)**
- **Best For:** Universal compatibility
- **Bitrate:** 32-320 kbps
- **VBR:** Supported via `-q` option

**libmp3lame Options:**
- `b`: Bitrate in bits/s for CBR/ABR
- `q`: 0-9 (VBR quality, 0=highest, 9=lowest)
- `compression_level`: 0-9 (algorithm quality, 0=best/slowest, 9=worst/fastest)
- `cutoff`: Lowpass cutoff frequency (auto if unspecified)
- `reservoir`: 0/1 (bit reservoir, default: 1)
- `joint_stereo`: 0/1 (L/R vs mid/side stereo, default: 1)
- `abr`: 0/1 (enable ABR mode)
- `copyright`: 0/1 (MPEG copyright flag, default: 0)
- `original`: 0/1 (MPEG original flag, default: 1)

#### **libshine (Fixed-Point MP3)**
- **Best For:** Embedded systems without FPU, ARM devices
- **Mode:** CBR only, stereo/mono only

**Options:**
- `b`: Bitrate in bits/s (FFmpeg) vs kbps (shineenc)

#### **Vorbis (libvorbis)**
- **Best For:** OGG containers, open-source
- **Quality:** VBR -1.0 to 10.0

**libvorbis Options:**
- `b`: Bitrate in bits/s for ABR mode
- `q`: -1.0 to 10.0 (VBR quality, default: 3.0)
- `cutoff`: Cutoff bandwidth in Hz (default: 0 = disabled)
- `minrate`: Minimum bitrate in bits/s
- `maxrate`: Maximum bitrate in bits/s (ABR mode only)
- `iblock`: -15.0 to 0.0 (impulse block noise floor bias)

#### **TwoLAME (MP2)**
- **Best For:** DAB radio, older broadcast
- **Bitrate:** Default 128 kbps

**libtwolame Options:**
- `b`: Bitrate in bits/s (default: 128k)
- `q`: -50 to 50 (experimental VBR, -10 to 10 useful, higher=better)
- `mode`: auto, stereo, joint_stereo, dual_channel, mono
- `psymodel`: -1 to 4 (psychoacoustic model, default: 3)
- `energy_levels`: 0/1 (energy levels extensions, default: 0)
- `error_protection`: 0/1 (CRC error protection, default: 0)
- `copyright`: 0/1 (MPEG copyright flag, default: 0)
- `original`: 0/1 (MPEG original flag, default: 0)

### Speech/Low-Bitrate Codecs

#### **AMR-NB (libopencore-amrnb)**
- **Best For:** Voice, telephony
- **Bitrate:** 4.75-12.2 kbps
- **Sample Rate:** 8000 Hz (mono only)

**Options:**
- `b`: 4750, 5150, 5900, 6700, 7400, 7950, 10200, 12200 bps
- `dtx`: 0/1 (discontinuous transmission, default: 0)

#### **AMR-WB (libvo-amrwbenc)**
- **Best For:** Wideband voice
- **Bitrate:** 6.6-23.85 kbps
- **Sample Rate:** 16000 Hz (mono only)

**Options:**
- `b`: 6600, 8850, 12650, 14250, 15850, 18250, 19850, 23050, 23850 bps
- `dtx`: 0/1 (discontinuous transmission, default: 0)

#### **iLBC (libilbc)**
- **Best For:** VoIP, Internet Low Bitrate
- **Frame Duration:** 20ms or 30ms

**Options:**
- `enhance`: 0/1 (audio enhancement, default: 0)

#### **LC3 (liblc3)**
- **Best For:** Bluetooth LE Audio, low complexity
- **Frame Duration:** 2.5, 5, 7.5, 10 ms

**liblc3 Options:**
- `b`: Bitrate in bits/s (determines frame size)
- `ar`: Sample rate in Hz
- `channels`: Number of channels
- `frame_duration`: 2.5, 5, 7.5, 10 ms (default: 10)
- `high_resolution`: 0/1 (HR mode for 48/96 kHz)

### Specialized Audio Codecs

#### **WavPack**
- **Encoder:** `wavpack`
- **Modes:** Lossless and lossy
- **Hybrid Mode:** Supported

**wavpack Options:**
- `frame_size`: 128-131072 (auto-calculated by default)
- `compression_level`: Mapped to -f, -h, -hh, -x flags
- `joint_stereo`: on(1), off(0), auto (mid/side encoding)
- `optimize_mono`: on/off (for non-mono streams)

#### **MPEG-H 3D Audio (libmpeghdec)**
- **Best For:** Immersive audio, spatial sound
- **Requires:** `--enable-libmpeghdec --enable-nonfree`

### Legacy/Compatibility Codecs

#### **CELT (libcelt)**
- **Best For:** Ultra-low delay (predecessor to Opus)

#### **GSM (libgsm)**
- **Best For:** Telephony compatibility
- **Variants:** GSM full rate, Microsoft GSM

---

## 3. HARDWARE ACCELERATION ENCODERS

### Intel QuickSync Video (QSV)

**Supported Codecs:** H.264, HEVC, MPEG-2, MJPEG, VP9, AV1, VVC
**Encoders:** `h264_qsv`, `hevc_qsv`, `mpeg2_qsv`, `mjpeg_qsv`, `vp9_qsv`, `av1_qsv`

#### Rate Control Methods (Auto-Selected):
1. **CQP** (Constant Quantizer): When `global_quality` is set with `qscale` flag
2. **LA_ICQ** (Lookahead ICQ): When `global_quality` + `look_ahead` are set
3. **ICQ** (Intelligent Constant Quality): When only `global_quality` is set (1-51 range)
4. **LA** (Lookahead VBR): When `b` + `look_ahead` are set
5. **VCM** (Video Conferencing): When `b` + `vcm` are set
6. **CBR** (Constant Bitrate): When `b` and `maxrate` are equal
7. **VBR** (Variable Bitrate): When `b` set and `maxrate` > `b`
8. **AVBR** (Average VBR): When `avbr_accuracy` and `avbr_convergence` are set (H.264/HEVC on Windows)

#### Common QSV Options:
- `async_depth`: Async operations before sync (parallelization depth)
- `preset`: veryfast, faster, fast, medium, slow, slower, veryslow
- `forced_idr`: Force I-frames as IDR frames
- `low_power`: Reduce power consumption/GPU usage
- `qsv_params`: Direct QSV parameters as key1=value1:key2=value2

#### H.264 QSV Options:
- `extbrc`: Extended bitrate control
- `recovery_point_sei`: Insert recovery point SEI at intra refresh cycles
- `rdo`: Rate distortion optimization
- `max_frame_size`: Maximum encoded frame size (bytes)
- `max_frame_size_i/p`: Maximum I/P frame sizes
- `max_slice_size`: Maximum slice size (bytes)
- `bitrate_limit`: Enforce QSV encoder bitrate range
- `mbbrc`: Macroblock-level bitrate control
- `low_delay_brc`: Low delay BRC (-1=default, 0=off, 1=on)
- `adaptive_i`: Allow P/B to I frame type changes
- `adaptive_b`: Allow B to P frame type changes
- `p_strategy`: 0=default, 1=simple, 2=pyramid (requires bf=0)
- `b_strategy`: B-frames as reference control
- `dblk_idc`: 0-2 (disable deblocking)
- `cavlc`: Use CAVLC instead of CABAC
- `vcm`: Video conferencing mode
- `idr_interval`: Distance between IDR frames (in I-frames)
- `pic_timing_sei`: Insert picture timing SEI
- `single_sei_nal_unit`: Put all SEI in one NALU
- `max_dec_frame_buffering`: Max DPB frames
- `look_ahead`: Enable VBR with look ahead
- `look_ahead_depth`: Look ahead depth in frames
- `look_ahead_downsampling`: unknown, auto, off, 2x, 4x
- `int_ref_type`: none, vertical, horizontal, slice
- `int_ref_cycle_size`: 2+ (refresh cycle pictures)
- `int_ref_qp_delta`: -51 to 51 (8-bit), -63 to 63 (10-bit), -75 to 75 (12-bit)
- `int_ref_cycle_dist`: Distance between refresh cycle starts
- `profile`: unknown, baseline, main, high
- `a53cc`: Use A53 closed captions
- `aud`: Insert Access Unit Delimiter NAL
- `mfmode`: off, auto (Multi-Frame Mode)
- `repeat_pps`: Repeat PPS for every frame
- `max_qp_i/p/b`: Maximum QP for I/P/B frames
- `min_qp_i/p/b`: Minimum QP for I/P/B frames
- `scenario`: unknown, displayremoting, videoconference, archive, livestreaming, cameracapture, videosurveillance, gamestreaming, remotegaming
- `avbr_accuracy`: AVBR accuracy (tenth of percent)
- `avbr_convergence`: AVBR convergence (unit of 100 frames)
- `skip_frame`: no_skip, insert_dummy, insert_nothing, brc_only

#### HEVC QSV Options:
- (Similar to H.264, plus:)
- `load_plugin`: none, hevc_sw, hevc_hw
- `load_plugins`: Colon-separated hexadecimal plugin UIDs
- `profile`: unknown, main, main10, mainsp, rext, scc (requires libmfx >= 1.32)
- `tier`: main, high (only level >= 4 supports high tier)
- `gpb`: 1=GPB (generalized P/B), 0=regular P
- `tile_cols/tile_rows`: Tiled encoding dimensions
- `transform_skip`: Enable transform skip (ICL+)
- `idr_interval`: Also supports 'begin_only' for single IDR at start

#### AV1 QSV Options:
- `profile`: unknown, main
- `tile_cols/tile_rows`: Tiled encoding
- `adaptive_i/b`: Frame type adaptation
- `b_strategy`: B-frame reference control
- `extbrc`: Extended bitrate control
- `look_ahead_depth`: Lookahead frames (when extbrc enabled)
- `low_delay_brc`: -1=default, 0=off, 1=on
- `max_frame_size`: Max frame size control
- `max_frame_size_i/p`: I/P-specific max sizes

### VAAPI (Video Acceleration API)

**Supported Codecs:** H.264, HEVC, MPEG-2, MJPEG, VP8, VP9, AV1
**Encoders:** `h264_vaapi`, `hevc_vaapi`, `mpeg2_vaapi`, `mjpeg_vaapi`, `vp8_vaapi`, `vp9_vaapi`, `av1_vaapi`
**Input:** VAAPI hardware surfaces only (use `hwupload` filter for software frames)

#### Common VAAPI Options:
- `low_power`: Use low-power encoder (may have reduced features)
- `idr_interval`: IDR frames between intra frames (open-GOP)
- `b_depth`: B-frame reference depth (1=default, higher=multi-layer)
- `async_depth`: Processing parallelism (requires vaSyncBuffer support)
- `max_frame_size`: Max frame size in bytes (invalid in CQP mode)
- `rc_mode`: auto, CQP, CBR, VBR, ICQ, QVBR, AVBR
- `blbrc`: Block-level rate control (invalid for CQP)

#### H.264 VAAPI:
- `coder`: ac/cabac (CABAC), vlc/cavlc (CAVLC)
- `aud`: Include access unit delimiters
- `sei`: identifier (encoder info), timing (buffering/pic timing), recovery_point

#### HEVC VAAPI:
- `aud`: Include access unit delimiters
- `tier`: Set general_tier_flag
- `sei`: hdr (HDR metadata: mastering display, content light level)
- `tiles`: columns x rows (parallel encoding/decoding)

#### MJPEG VAAPI:
- Baseline DCT only
- Standard quantization/huffman tables
- YUV: 4:2:0, 4:2:2, 4:4:4 supported
- RGB JPEG supported
- `jfif`: Include JFIF header
- `huffman`: Include standard huffman tables (default: on)

#### VP8 VAAPI:
- No B-frames support
- `global_quality`: q_idx for non-key frames (0-127)
- `loop_filter_level/sharpness`: Manual loop filter control

#### VP9 VAAPI:
- `global_quality`: q_idx for P-frames (0-255)
- `loop_filter_level/sharpness`: Manual loop filter
- B-frames supported (encode order, not display order)
- May require `vp9_raw_reorder` and `vp9_superframe` bitstream filters

#### AV1 VAAPI:
- `profile`: Sets seq_profile
- `tier`: Sets seq_tier
- `level`: Sets seq_level_idx
- `tiles`: columns x rows (default: auto = minimal)
- `tile_groups`: Tile group count (default: 1, evenly distributed)

### MediaFoundation (Windows)

**Supported Codecs:** H.264, HEVC, AV1
**Encoders:** `h264_mf`, `hevc_mf`, `av1_mf`
**Hardware:** Software and hardware encoding
**Input Formats:** nv12 (safer), yuv420p
**Hardware Acceleration:** Requires D3D11, use `scale_d3d11` filter

#### MediaFoundation Options:
- `rate_control`: default, cbr, pc_vbr, u_vbr, quality, ld_vbr (Win8+), g_vbr (Win8+), gld_vbr (Win8+)
- `scenario`: default, display_remoting, video_conference, archive, live_streaming, camera_record, display_remoting_with_feature_map
- `quality`: 0-100 (-1 = default quality)
- `hw_encoding`: 0/1 (force hardware encoding, default: 0)

### MediaCodec (Android)

**Supported Codecs:** H.264, HEVC, VP8, VP9, MPEG-4, AV1
**APIs:** Java MediaCodec, NDK MediaCodec
**Device-Dependent:** Codec support varies by Android device

#### MediaCodec Options:
- `ndk_codec`: Use NDK API instead of Java (default: auto if no JVM)
- `ndk_async`: Use NDK async mode (default: auto, disabled on Android <8.0)
- `codec_name`: Specify backend via MediaCodec createCodecByName
- `bitrate_mode`: cq (constant quality), vbr, cbr, cbr_fd (with frame drops)
- `pts_as_dts`: Use PTS as DTS workaround (auto-enabled if bf=0)
- `operating_rate`: Desired operating rate (e.g., high-speed capture)
- `qp_i/p/b_min/max`: Min/max quantization parameters for I/P/B frames

### Important Hardware Encoder Notes:

1. **NVENC/VideoToolbox/AMF:** Not present in this documentation file. These may be documented separately or in encoder-specific docs.

2. **QSV Global to MSDK Mapping:**
   - `g/gop_size` → GopPicSize
   - `bf/max_b_frames+1` → GopRefDist
   - `rc_init_occupancy` → InitialDelayInKB
   - `slices` → NumSlice
   - `refs` → NumRefFrame
   - `b_strategy` → BRefType
   - `cgop/CLOSED_GOP` flag → GopOptFlag
   - CQP mode: `i_qfactor/i_qoffset` and `b_qfactor/b_qoffset` set QP differences
   - `coder=vlc` → Use CAVLC instead of CABAC (H.264)

3. **Performance Tips:**
   - QSV: Set verbosity to verbose or higher to see actual settings used
   - VAAPI: Ensure sufficient `hw_frames` for high `async_depth`
   - MediaFoundation: Use D3D11 hardware acceleration pipeline for best performance

---

## 4. QUALITY SETTINGS & RATE CONTROL

### CRF (Constant Rate Factor) - Recommended

**Best Quality/Size Balance**

#### H.264 (libx264):
- Range: 0-51
- **0**: Lossless (huge files)
- **17-18**: Visually lossless (very high quality)
- **23**: Default, good quality
- **28**: Acceptable quality for web
- **51**: Worst quality

**Recommended Values:**
- Archival/Master: 15-18
- High Quality: 18-23
- Streaming/Web: 23-28
- Low Bandwidth: 28-35

#### HEVC (libx265):
- Range: 0-51
- Similar quality perception to H.264 at same CRF
- **28** HEVC ≈ **23** H.264 (similar visual quality)

**Recommended Values:**
- Archival: 18-22
- High Quality: 22-28
- Streaming: 28-32
- Low Bandwidth: 32-38

#### AV1:
- Range: 0-63
- **0**: Lossless
- **23**: Default for libaom-av1
- Higher values = lower quality

**Recommended Values (libaom-av1):**
- High Quality: 15-25
- Streaming: 25-35
- Low Bandwidth: 35-45

#### VP9:
- Range: 0-63 (libvpx)
- **31**: Default
- Lower values = better quality

**Recommended Values:**
- High Quality: 15-25
- Streaming: 25-35
- Low Bandwidth: 35-50

### Bitrate Modes

#### 1. CBR (Constant Bitrate)
**Use Case:** Streaming, broadcast (predictable bandwidth)

**Settings:**
```bash
-b:v 5000k -minrate 5000k -maxrate 5000k -bufsize 10000k
```

**Advantages:**
- Predictable file size
- Streaming-friendly
- Network-friendly

**Disadvantages:**
- Less efficient compression
- Quality varies with scene complexity

#### 2. VBR (Variable Bitrate)
**Use Case:** File storage, video-on-demand

**Settings:**
```bash
-b:v 5000k -maxrate 8000k -bufsize 10000k
```

**Advantages:**
- Better quality/size ratio
- Adapts to scene complexity

**Disadvantages:**
- Unpredictable file size
- May cause streaming issues

#### 3. ABR (Average Bitrate)
**Use Case:** Balance between CBR and VBR

**Settings:**
```bash
-b:v 5000k
```

#### 4. CQP (Constant Quantization Parameter)
**Use Case:** Consistent quality across frames

**Settings:**
```bash
-qp 23
```

**Advantages:**
- Consistent quality
- Fast encoding

**Disadvantages:**
- Unpredictable bitrate/file size

#### 5. Constrained Quality (CRF + Maxrate)
**Use Case:** Quality target with bitrate ceiling

**Settings:**
```bash
-crf 23 -maxrate 8000k -bufsize 16000k
```

### Two-Pass Encoding

**Best Quality for Target Bitrate**

**First Pass (Analysis):**
```bash
-pass 1 -passlogfile output -b:v 5000k -an -f null /dev/null
```

**Second Pass (Encoding):**
```bash
-pass 2 -passlogfile output -b:v 5000k -c:a aac -b:a 192k output.mp4
```

**Advantages:**
- Optimal bitrate distribution
- Better quality than single-pass at same bitrate
- Precise file size control

**Disadvantages:**
- Twice the encoding time
- Requires two passes

### Quantization Parameters

#### QP Ranges:
- **H.264/HEVC:** 0-51
- **AV1:** 0-63
- **VP8/VP9:** 0-63
- **MPEG-2:** 1-31

#### QP Guidelines:
- **Lower QP** = Higher quality, larger file
- **Higher QP** = Lower quality, smaller file
- **QP 0** = Often lossless (codec-dependent)

#### Per-Frame Type QP Control:
```bash
-qmin 10 -qmax 51 -i_qfactor 0.71 -b_qfactor 1.3
```

- `i_qfactor`: I-frame QP multiplier (default: 0.71, lower = better I-frames)
- `b_qfactor`: B-frame QP multiplier (default: 1.3, higher = more compression)
- `qmin/qmax`: Constrain QP range

### Adaptive Quantization (AQ)

#### H.264/H.265 (x264/x265):
```bash
-aq-mode 1 -aq-strength 1.0
```

**AQ Modes:**
- **0**: Disabled
- **1**: Variance-based (default for x264) - reduces blocking/blurring
- **2**: Auto-variance (experimental)
- **3**: Adaptive QP based on psychovisual properties (x265 only)

**AQ Strength:** 0.0-3.0 (1.0 = default)

#### VP9:
```bash
-aq-mode 3
```

**Modes:** 0=off, 1=variance, 2=complexity, 3=cyclic refresh, 4=equator360

#### AV1 (libaom):
```bash
-aq-mode 1
```

**Modes:** 0=none, 1=variance, 2=complexity, 3=cyclic

### Rate Control Buffer (VBV)

**Prevents bitrate spikes/drops**

```bash
-maxrate 8000k -bufsize 16000k
```

**Buffer Size Guidelines:**
- **1x maxrate**: Strict control (good for streaming)
- **2x maxrate**: Balanced
- **4x maxrate**: Loose control (better quality)

### Lookahead

**Improves rate control decisions**

#### X264:
```bash
-rc-lookahead 40
```
- Range: 0-250 frames
- Default: 40
- Higher = better quality (diminishing returns >60)

#### X265:
- Automatically managed by preset

#### QSV:
```bash
-look_ahead 1 -look_ahead_depth 40
```

#### AV1 (libaom):
```bash
-lag-in-frames 25
```

---

## 5. CODEC COMPATIBILITY MATRIX

### Container Support

| Codec | MP4 | MKV | WebM | AVI | MOV | OGG | FLV | MPEG-TS |
|-------|-----|-----|------|-----|-----|-----|-----|---------|
| **H.264/AVC** | ✓ | ✓ | - | ✓ | ✓ | - | ✓ | ✓ |
| **H.265/HEVC** | ✓ | ✓ | - | - | ✓ | - | - | ✓ |
| **AV1** | ✓ | ✓ | ✓ | - | ✓ | - | - | ✓ |
| **VP8** | - | ✓ | ✓ | ✓ | - | - | ✓ | - |
| **VP9** | ✓ | ✓ | ✓ | - | - | - | - | - |
| **MPEG-2** | ✓ | ✓ | - | ✓ | ✓ | - | - | ✓ |
| **MPEG-4 Part 2** | ✓ | ✓ | - | ✓ | ✓ | - | ✓ | ✓ |
| **ProRes** | - | ✓ | - | - | ✓ | - | - | - |
| **DNxHD/DNxHR** | - | ✓ | - | - | ✓ | - | - | - |
| **FFV1** | - | ✓ | - | ✓ | - | - | - | - |
| **Theora** | - | ✓ | - | - | - | ✓ | - | - |
| **JPEG2000** | ✓ | ✓ | - | ✓ | ✓ | - | - | - |

### Audio Container Support

| Codec | MP4 | MKV | WebM | AVI | MOV | OGG | M4A | ADTS |
|-------|-----|-----|------|-----|-----|-----|-----|------|
| **AAC** | ✓ | ✓ | - | ✓ | ✓ | - | ✓ | ✓ |
| **Opus** | ✓ | ✓ | ✓ | - | - | ✓ | - | - |
| **Vorbis** | - | ✓ | ✓ | - | - | ✓ | - | - |
| **MP3** | ✓ | ✓ | - | ✓ | ✓ | - | - | ✓ |
| **FLAC** | ✓ | ✓ | - | ✓ | ✓ | ✓ | - | - |
| **AC-3** | ✓ | ✓ | - | ✓ | ✓ | - | - | ✓ |
| **PCM** | ✓ | ✓ | - | ✓ | ✓ | - | - | - |

### Platform/Browser Compatibility

#### Video Codecs:

**Universal (99%+ support):**
- H.264 (Baseline/Main profile)
- MPEG-4 Part 2

**Modern Browsers (95%+):**
- H.264 (High profile)
- VP8
- VP9

**Cutting Edge (70-90%):**
- HEVC (Safari, Edge on Windows 10+)
- AV1 (Chrome 70+, Firefox 67+, Edge 79+)

**Professional/Niche:**
- ProRes (Apple ecosystem, professional tools)
- DNxHD (Avid, professional NLEs)
- FFV1 (Archival, limited player support)

#### Audio Codecs:

**Universal:**
- AAC-LC
- MP3

**Modern:**
- Opus (best for web, not in Safari)
- Vorbis (open-source, declining)

**Professional:**
- FLAC (lossless, growing support)
- AC-3/E-AC-3 (broadcast, surround)
- PCM (uncompressed, universal)

### Hardware Decoder Support

| Codec | Hardware Decode Available |
|-------|--------------------------|
| **H.264** | Universal (all platforms) |
| **HEVC** | Modern GPUs (2015+), Mobile (2017+) |
| **VP9** | Modern GPUs (2016+), Mobile (2018+) |
| **AV1** | Latest GPUs (2020+), Mobile (2021+) |
| **MPEG-2** | Widespread (legacy support) |

### Profile/Level Compatibility

#### H.264 Profiles:
- **Baseline:** Maximum compatibility (old devices, streaming)
- **Main:** Standard compatibility (TV, set-top boxes)
- **High:** Best compression (modern devices)
- **High 10:** 10-bit color (professional, limited hardware)

#### HEVC Profiles:
- **Main:** 8-bit, 4:2:0 (standard)
- **Main 10:** 10-bit, 4:2:0 (HDR, UHD)
- **Main 12:** 12-bit
- **Main 4:4:4:** No chroma subsampling

#### AV1 Profiles:
- **Main:** 8/10-bit, 4:2:0/4:0:0
- **High:** 8/10-bit, 4:4:4
- **Professional:** 8/10/12-bit, all chroma formats

---

## 6. LOSSLESS VS LOSSY OPTIONS

### Lossless Video Codecs

#### **FFV1** (Recommended for archival)
**Container:** MKV, AVI

**Settings:**
```bash
-c:v ffv1 -level 3 -coder 1 -context 1 -g 1 -slices 24 -slicecrc 1
```

**Options:**
- `level`: 0, 1, 3 (3 = latest, best compression)
- `coder`: 0=Golomb-Rice, 1=range coder (better compression)
- `context`: 0=small, 1=large (large = better compression)
- `slices`: 4-1024 (more = better multi-threading)
- `slicecrc`: 1=enabled (error detection)

**Characteristics:**
- Best compression among lossless codecs
- Error resilience
- Good multi-threading
- Archival standard

#### **UT Video**
**Best For:** Fast encoding/decoding

**Settings:**
```bash
-c:v utvideo -pred left
```

**Characteristics:**
- Very fast
- Moderate compression
- Good for editing proxies

#### **HuffYUV**
**Best For:** Legacy compatibility

**Settings:**
```bash
-c:v huffyuv
```

**Characteristics:**
- Fast encoding/decoding
- Limited compression
- Widely supported in NLEs

#### **Lossless H.264**
**Settings:**
```bash
-c:v libx264 -qp 0 -preset veryslow
```

**Characteristics:**
- Good compression
- Wide hardware decode support
- Slower encoding than FFV1

#### **Lossless HEVC**
**Settings:**
```bash
-c:v libx265 -x265-params lossless=1
```

**Characteristics:**
- Better compression than H.264
- Less hardware support
- Slower encoding

#### **Lossless VP9**
**Settings:**
```bash
-c:v libvpx-vp9 -lossless 1
```

#### **JPEG2000 Lossless**
**Settings:**
```bash
-c:v jpeg2000 -pred 1
```
- `pred 1` = dwt53 (lossless transform)

**Best For:** Digital cinema, archival

#### **JPEG XL Lossless**
**Settings:**
```bash
-c:v libjxl -distance 0.0
```

**Best For:** Modern archival, next-gen format

### Lossless Audio Codecs

#### **FLAC** (Recommended)
**Settings:**
```bash
-c:a flac -compression_level 12
```

**Compression Levels:** 0-12 (12 = slowest/best, 5 = default)

**Characteristics:**
- Excellent compression
- Fast decoding
- Wide support
- Metadata support

#### **ALAC (Apple Lossless)**
**Settings:**
```bash
-c:a alac
```

**Characteristics:**
- Apple ecosystem
- Similar compression to FLAC
- Good iTunes/iOS support

#### **WavPack Lossless**
**Settings:**
```bash
-c:a wavpack
```

**Characteristics:**
- Excellent compression
- Hybrid mode support
- Correction files

#### **TTA (True Audio)**
**Settings:**
```bash
-c:a tta
```

**Characteristics:**
- Good compression
- Fast
- Limited support

#### **PCM (Uncompressed)**
**Settings:**
```bash
-c:a pcm_s16le    # 16-bit
-c:a pcm_s24le    # 24-bit
-c:a pcm_s32le    # 32-bit
-c:a pcm_f32le    # 32-bit float
```

**Best For:** Maximum compatibility, editing

### Visually Lossless (Near-Lossless)

#### **H.264**
```bash
-c:v libx264 -crf 15 -preset veryslow
```
- CRF 15-18: Visually indistinguishable from lossless
- ~50-70% file size of true lossless

#### **HEVC**
```bash
-c:v libx265 -crf 18 -preset veryslow
```
- CRF 18-22: Visually indistinguishable
- Better compression than H.264

#### **ProRes 4444 XQ**
```bash
-c:v prores_ks -profile:v 4444xq
```
- Mathematically lossy, visually lossless
- Professional standard

### Hybrid Modes

#### **WavPack Hybrid**
**Create lossy + correction file:**
```bash
# Lossy file
-c:a wavpack -compression_level 8

# Correction file (combine for lossless)
wavpack -c input.wav -o output.wv
```

### Compression Comparison (Same Source)

**Lossless Video (1080p30, 1min, YUV420):**
- Uncompressed: ~3.5 GB
- FFV1 level 3: ~500-800 MB
- Lossless H.264: ~600-900 MB
- HuffYUV: ~1-1.5 GB
- UT Video: ~800-1200 MB

**Visually Lossless:**
- H.264 CRF 15: ~200-400 MB
- HEVC CRF 18: ~150-300 MB
- ProRes HQ: ~800-1200 MB

**Lossless Audio (44.1kHz stereo, 1min):**
- PCM: ~10 MB
- FLAC: ~5-7 MB
- ALAC: ~5-7 MB
- WavPack: ~5-6.5 MB

---

## 7. BEST PRACTICES BY OUTPUT FORMAT

### MP4 (Web, Mobile, Streaming)

**Recommended Settings:**

**Video:**
```bash
# Maximum Compatibility
-c:v libx264 -preset medium -crf 23 -profile:v high -level 4.0 -pix_fmt yuv420p

# High Quality
-c:v libx264 -preset slow -crf 18 -profile:v high -level 4.1

# 4K/HEVC
-c:v libx265 -preset medium -crf 28 -tag:v hvc1 -pix_fmt yuv420p10le

# AV1 (Future)
-c:v libsvtav1 -crf 30 -preset 6
```

**Audio:**
```bash
# Standard Quality
-c:a aac -b:a 128k

# High Quality
-c:a aac -b:a 192k -profile:a aac_low

# Stereo Music
-c:a aac -b:a 256k

# Surround 5.1
-c:a ac3 -b:a 640k
```

**Container Flags:**
```bash
-movflags +faststart    # Enable streaming before download complete
-movflags +write_colr   # Write color information
```

**Best Practices:**
- Always use `-pix_fmt yuv420p` for maximum compatibility
- Use `-profile:v high -level 4.0` for wide device support
- Use `-profile:v baseline` for oldest devices
- Add `-movflags +faststart` for web streaming
- For HEVC, use `-tag:v hvc1` for better compatibility

### MKV (Archival, Multi-Track, Chapters)

**Recommended Settings:**

**Video:**
```bash
# Lossless Archival
-c:v ffv1 -level 3 -coder 1 -context 1 -slices 24 -slicecrc 1

# High Quality Lossy
-c:v libx265 -crf 18 -preset slow -x265-params log-level=error

# Master Copy
-c:v prores_ks -profile:v hq
```

**Audio:**
```bash
# Lossless
-c:a flac -compression_level 12

# Multiple Audio Tracks
-map 0:v -map 0:a:0 -map 0:a:1 -c:a:0 flac -c:a:1 ac3 -b:a:1 640k

# Multi-language
-metadata:s:a:0 language=eng -metadata:s:a:1 language=jpn
```

**Subtitles:**
```bash
# Embed subtitles
-c:s srt

# Multiple subtitle tracks
-map 0:s -c:s copy -metadata:s:s:0 language=eng
```

**Best Practices:**
- MKV supports virtually all codecs
- Use for multi-track audio (original + commentary)
- Good for chapters and complex metadata
- Supports multiple subtitle tracks/fonts
- Use FFV1 for lossless archival with error resilience

### WebM (Web Streaming, HTML5)

**Recommended Settings:**

**Video:**
```bash
# VP9 High Quality
-c:v libvpx-vp9 -crf 30 -b:v 0 -deadline good -cpu-used 2 -row-mt 1

# VP9 Two-Pass
-c:v libvpx-vp9 -b:v 2M -deadline good -cpu-used 2 -row-mt 1 -pass 1
-c:v libvpx-vp9 -b:v 2M -deadline good -cpu-used 2 -row-mt 1 -pass 2

# AV1 (Next-gen)
-c:v libsvtav1 -crf 35 -preset 8
```

**Audio:**
```bash
# Opus (Recommended)
-c:a libopus -b:a 128k -vbr on -compression_level 10

# Vorbis (Older)
-c:a libvorbis -q:a 5
```

**Best Practices:**
- WebM only supports VP8/VP9/AV1 video
- Opus is preferred over Vorbis (better quality)
- Use `-row-mt 1` for VP9 multi-threading
- Two-pass encoding recommended for streaming
- Use `-deadline good` for balanced speed/quality

### MOV (ProRes, Professional, Apple Ecosystem)

**Recommended Settings:**

**ProRes:**
```bash
# ProRes 422 (Standard)
-c:v prores_ks -profile:v standard -vendor apl0

# ProRes 422 HQ (High Quality)
-c:v prores_ks -profile:v hq -vendor apl0

# ProRes 4444 (Alpha)
-c:v prores_ks -profile:v 4444 -alpha_bits 16 -vendor apl0

# ProRes 4444 XQ (Extreme Quality)
-c:v prores_ks -profile:v 4444xq -vendor apl0
```

**Audio:**
```bash
# PCM (Uncompressed)
-c:a pcm_s24le

# AAC
-c:a aac -b:a 256k
```

**Best Practices:**
- MOV is Apple's container (QuickTime)
- ProRes is industry standard for editing
- Use `-vendor apl0` for Apple compatibility
- ProRes 422 HQ is sweet spot for quality/size
- ProRes 4444/XQ for effects work or HDR
- Always use PCM or high-bitrate AAC for audio

### AVI (Legacy, Compatibility)

**Recommended Settings:**

**Video:**
```bash
# Lossless (HuffYUV)
-c:v huffyuv

# Lossless (FFV1)
-c:v ffv1 -level 3

# Lossy (Xvid)
-c:v libxvid -q:v 3

# Lossy (H.264)
-c:v libx264 -crf 23
```

**Audio:**
```bash
# PCM
-c:a pcm_s16le

# MP3
-c:a libmp3lame -b:a 192k

# AC-3
-c:a ac3 -b:a 448k
```

**Best Practices:**
- AVI is legacy format (avoid for new projects)
- Limited to 2GB per file (use AVI2/OpenDML for larger)
- Use for compatibility with very old software
- HuffYUV/FFV1 for lossless capture
- Consider MKV or MP4 instead

### OGG/OGV (Open Source, Theora)

**Recommended Settings:**

**Video:**
```bash
# Theora
-c:v libtheora -q:v 7
```

**Audio:**
```bash
# Vorbis
-c:a libvorbis -q:a 6

# Opus
-c:a libopus -b:a 128k
```

**Best Practices:**
- Open-source, patent-free
- Declining usage (WebM is successor)
- Theora is outdated (use VP9 instead)
- Good for Vorbis/Opus audio streaming
- Consider WebM for modern use

### MPEG-TS (Broadcast, Streaming)

**Recommended Settings:**

**Video:**
```bash
# H.264 for broadcast
-c:v libx264 -preset medium -b:v 5000k -maxrate 5000k -bufsize 10000k -profile:v high -level 4.0

# HEVC for 4K broadcast
-c:v libx265 -preset medium -b:v 15000k -maxrate 15000k -bufsize 30000k

# MPEG-2 for legacy broadcast
-c:v mpeg2video -b:v 8000k -maxrate 8000k -bufsize 16000k -profile:v high -level high
```

**Audio:**
```bash
# AAC (Modern)
-c:a aac -b:a 192k

# AC-3 (Broadcast)
-c:a ac3 -b:a 384k

# MPEG Audio (Legacy)
-c:a mp2 -b:a 192k
```

**Muxer Options:**
```bash
-f mpegts -mpegts_service_type digital_tv -mpegts_pmt_start_pid 0x1000
```

**Best Practices:**
- MPEG-TS designed for broadcast/streaming
- Use CBR for consistent streaming
- Supports multiple programs/streams
- Good for live streaming (HLS, MPEG-DASH)
- Use high profile H.264 or HEVC for efficiency

---

## 8. COMPLETE CODEC DETAILS

### DETAILED CODEC OPTIONS

#### libx264 (H.264) - EXHAUSTIVE OPTIONS

**Basic Rate Control:**
```bash
-b:v <bitrate>          # Target bitrate (bits/s)
-crf <0-51>             # Constant Rate Factor (18-28 typical)
-qp <0-51>              # Constant Quantizer Parameter
-minrate <bitrate>      # Minimum bitrate
-maxrate <bitrate>      # Maximum bitrate
-bufsize <size>         # Rate control buffer size
-crf_max <0-51>         # Maximum CRF (in VBR mode)
```

**Presets (Speed/Efficiency):**
```
ultrafast, superfast, veryfast, faster, fast, medium (default), slow, slower, veryslow, placebo
```

**Tuning:**
```
film, animation, grain, stillimage, psnr, ssim, fastdecode, zerolatency
```

**Profiles:**
```
baseline, main, high, high10, high422, high444
```

**Level:**
```
-level 3.0, 3.1, 4.0, 4.1, 4.2, 5.0, 5.1, 5.2, 6.0, 6.1, 6.2
```

**GOP Structure:**
```bash
-g <int>                # GOP size (keyframe interval)
-keyint_min <int>       # Minimum GOP size
-bf <0-16>              # B-frames (0=disabled, -1=auto)
-b_strategy <0-2>       # B-frame placement (0=disabled, 1=fast, 2=optimal)
-refs <0-16>            # Reference frames
-b-pyramid <none|strict|normal>  # B-frame pyramid
```

**Motion Estimation:**
```bash
-me_method <method>     # dia, hex, umh, esa, tesa
-me_range <int>         # Motion search range (pixels)
-subq <0-11>            # Sub-pixel ME quality
-trellis <0-2>          # Rate-distortion optimization
```

**Adaptive Quantization:**
```bash
-aq-mode <0-2>          # 0=off, 1=variance, 2=auto-variance
-aq-strength <0.0-3.0>  # AQ strength (1.0=default)
```

**Psychovisual Optimization:**
```bash
-psy <0|1>              # Enable psychovisual optimizations
-psy-rd <float:float>   # psy-rd:psy-trellis (1.0:0.15 default)
```

**Deblocking Filter:**
```bash
-deblock <alpha:beta>   # Loop filter (-6:6 range, 0:0=default)
```

**Entropy Coding:**
```bash
-coder <0|1|ac|vlc>     # 0/vlc=CAVLC, 1/ac=CABAC
```

**Partitions:**
```bash
-partitions <list>      # p8x8,p4x4,b8x8,i8x8,i4x4,none,all
-8x8dct <0|1>           # Enable 8x8 DCT (high profile)
```

**Weighted Prediction:**
```bash
-weightb <0|1>          # Weighted prediction for B-frames
-weightp <0-2>          # 0=off, 1=simple, 2=smart
```

**Intra Refresh:**
```bash
-intra-refresh <0|1>    # Periodic intra refresh instead of IDR
```

**Rate Control Lookahead:**
```bash
-rc-lookahead <0-250>   # Frames to look ahead (40=default)
```

**Macroblock Tree:**
```bash
-mbtree <0|1>           # Macroblock tree rate control
```

**Fast Skip:**
```bash
-fast-pskip <0|1>       # Fast P-frame SKIP detection
```

**Mixed References:**
```bash
-mixed-refs <0|1>       # One reference per partition
```

**Chroma ME:**
```bash
-cmp <sad|chroma>       # Include chroma in motion estimation
```

**Direct Mode:**
```bash
-direct-pred <none|spatial|temporal|auto>
```

**Slice Options:**
```bash
-slices <int>           # Number of slices
-slice-max-size <bytes> # Maximum slice size
```

**NAL HRD:**
```bash
-nal-hrd <none|vbr|cbr> # NAL HRD signaling
```

**Frame Threading:**
```bash
-threads <int>          # Number of threads (0=auto)
-thread_type <slice|frame>
```

**Color Options:**
```bash
-pix_fmt <format>       # yuv420p, yuv422p, yuv444p, etc.
-colorspace <space>     # bt709, bt470bg, smpte170m, bt2020nc
-color_primaries <prim> # bt709, bt2020, etc.
-color_trc <trc>        # bt709, smpte2084 (HDR10), arib-std-b67 (HLG)
-color_range <range>    # tv (limited), pc (full)
```

**Flags:**
```bash
-flags +cgop            # Closed GOP
-flags -cgop            # Open GOP
-flags +global_header   # Global header in extradata
```

**Bitstream Filters:**
```bash
-x264opts <key=value:...>   # Advanced x264 options
-x264-params <key=value:...> # Same as x264opts
```

**Quality Metrics:**
```bash
-ssim <0|1>             # Calculate SSIM
```

**Closed Captions:**
```bash
-a53cc <0|1>            # Import A53 closed captions
```

**SEI:**
```bash
-udu_sei <0|1>          # Import user data unregistered SEI
```

**AVC-Intra:**
```bash
-avcintra-class <50|100|200>  # AVC-Intra mode
```

**Blu-ray Compatibility:**
```bash
-bluray-compat <0|1>    # Blu-ray compatibility mode
```

**B-frame Bias:**
```bash
-b-bias <int>           # B-frame usage influence
```

**Complexity Blur:**
```bash
-cplxblur <float>       # QP fluctuation reduction
```

**Access Unit Delimiters:**
```bash
-aud <0|1>              # Insert AUD NAL units
```

#### libx265 (HEVC) - EXHAUSTIVE OPTIONS

**Basic Rate Control:**
```bash
-b:v <bitrate>          # Target bitrate
-crf <0-51>             # Constant Rate Factor
-qp <0-51>              # Constant QP
-qmin <0-51>            # Minimum QP
-qmax <0-51>            # Maximum QP
-qdiff <int>            # Max QP difference
```

**Presets:**
```
ultrafast, superfast, veryfast, faster, fast, medium (default), slow, slower, veryslow, placebo
```

**Tuning:**
```
psnr, ssim, grain, zerolatency, fastdecode
```

**Profiles:**
```
main, main10, main12, main444-8, main444-10, main444-12, main-intra, main10-intra
```

**GOP Structure:**
```bash
-g <int>                # GOP size
-keyint_min <int>       # Minimum GOP size
-bf <int>               # B-frames
-refs <1-16>            # Reference frames
```

**Advanced Options:**
```bash
-i_qfactor <float>      # I-frame QP factor
-b_qfactor <float>      # B-frame QP factor
-qblur <float>          # Quantizer blur
-qcomp <float>          # Quantizer compression
```

**Forced IDR:**
```bash
-forced-idr <0|1>       # Force IDR frames
```

**User Data SEI:**
```bash
-udu_sei <0|1>          # Import user data SEI
```

**x265 Parameters:**
```bash
-x265-params <key=value:...>
```

**Common x265-params:**
```
crf=<0-51>
preset=<ultrafast...placebo>
tune=<psnr|ssim|grain|zerolatency|fastdecode>
profile=<main|main10|main444-8>
level-idc=<3.0...6.2>
high-tier=<0|1>
psy-rd=<float>
psy-rdoq=<float>
aq-mode=<0-4>
aq-strength=<float>
deblock=<int:int>
sao=<0|1>
signhide=<0|1>
b-intra=<0|1>
b-adapt=<0-2>
bframes=<0-16>
rc-lookahead=<10-250>
lookahead-slices=<0-16>
scenecut=<0-60>
radl=<int>
intra-refresh=<0|1>
ctu=<16|32|64>
min-cu-size=<8|16|32>
rect=<0|1>
amp=<0|1>
limit-modes=<0|1>
me=<0-4>  # 0=dia, 1=hex, 2=umh, 3=star, 4=full
merange=<int>
subme=<0-7>
max-merge=<1-5>
temporal-mvp=<0|1>
weightp=<0|1>
weightb=<0|1>
strong-intra-smoothing=<0|1>
constrained-intra=<0|1>
lossless=<0|1>
cu-lossless=<0|1>
rdpenalty=<0-2>
rdoq-level=<0-2>
psy-rd=<0.0-5.0>
psy-rdoq=<0.0-50.0>
cbqpoffs=<-12-12>
crqpoffs=<-12-12>
nr-intra=<0-2000>
nr-inter=<0-2000>
pools=<string>
numa-pools=<string>
asm=<0-10>
frame-threads=<0-16>
max-cu-size=<16|32|64>
vbv-bufsize=<int>
vbv-maxrate=<int>
vbv-init=<0.0-1.0>
pass=<1-3>
slow-firstpass=<0|1>
stats=<filename>
analysis-reuse-mode=<off|load|save>
analysis-save=<filename>
analysis-load=<filename>
strict-cbr=<0|1>
qg-size=<8|16|32|64>
rc=<cqp|crf|abr>
bitrate=<int>
qpmin=<0-51>
qpmax=<0-51>
ipratio=<float>
pbratio=<float>
aq-mode=<0|1|2|3|4>  # 0=off, 1=variance, 2=auto-variance, 3=auto-variance-biased, 4=auto-variance-darker
hevc-aq=<0|1>
qp-adaptation-range=<float>
scenecut-bias=<0.0-100.0>
hist-scenecut=<0|1>
hist-threshold=<0.0-1.0>
radl=<0-INT_MAX>
ctu-info=<0-6>
```

#### libaom-av1 - EXHAUSTIVE OPTIONS

**Rate Control:**
```bash
-b:v <bitrate>          # Target bitrate (VBR)
-crf <0-63>             # Constant quality (0=lossless, 23=default)
-qmin <0-63>            # Minimum quantizer
-qmax <0-63>            # Maximum quantizer
-minrate <bitrate>      # Minimum bitrate
-maxrate <bitrate>      # Maximum bitrate
-bufsize <size>         # Rate control buffer
```

**Speed/Quality:**
```bash
-cpu-used <0-8>         # 0=slowest/best, 8=fastest/worst, 1=default
```

**GOP Structure:**
```bash
-g <int>                # GOP size (keyframe interval)
-keyint_min <int>       # Minimum GOP size
```

**Threading:**
```bash
-threads <int>          # Encoding threads (default: auto)
-tiles <cols x rows>    # Tile configuration (e.g., 2x2)
-tile-columns <0-6>     # log2 of tile columns
-tile-rows <0-6>        # log2 of tile rows
-row-mt <0|1>           # Row-based multi-threading
```

**Profile:**
```bash
-profile <0|1|2>        # 0=main, 1=high, 2=professional
```

**Alternate Reference Frames:**
```bash
-auto-alt-ref <0|1>     # Enable alternate reference frames
-arnr-max-frames <int>  # Max frames for ARF filtering
-arnr-strength <0-6>    # ARF filter strength
```

**Adaptive Quantization:**
```bash
-aq-mode <0-3>          # 0=off, 1=variance, 2=complexity, 3=cyclic
```

**Tuning:**
```bash
-tune <psnr|ssim>       # Optimize for metric
```

**Lookahead:**
```bash
-lag-in-frames <0-70>   # Number of lookahead frames
```

**Error Resilience:**
```bash
-error-resilience <default>  # Enable error resilience
```

**Static Threshold:**
```bash
-static-thresh <int>    # Block skip threshold (0=default)
```

**Drop Threshold:**
```bash
-drop-threshold <0-100> # Frame drop threshold (%)
```

**Denoising:**
```bash
-denoise-noise-level <0-50>  # Noise removal level (0=disabled)
-denoise-block-size <int>    # Denoising block size (32=default)
```

**Rate Control:**
```bash
-undershoot-pct <-1-100>     # Undershoot % (-1=default)
-overshoot-pct <-1-1000>     # Overshoot % (-1=default)
-minsection-pct <-1-100>     # Min GOP bitrate % (-1=auto)
-maxsection-pct <-1-5000>    # Max GOP bitrate % (-1=auto)
```

**Frame Parallel:**
```bash
-frame-parallel <0|1>   # Frame parallel decoding (default: 1)
```

**CDEF (Constrained Directional Enhancement Filter):**
```bash
-enable-cdef <0|1>      # Default: 1
```

**Loop Restoration:**
```bash
-enable-restoration <0|1>  # Default: 1
```

**Global Motion:**
```bash
-enable-global-motion <0|1>  # Default: 1
```

**Intra Block Copy:**
```bash
-enable-intrabc <0|1>   # For screen content (default: 1)
```

**Rectangular Partitions:**
```bash
-enable-rect-partitions <0|1>     # Default: 1
-enable-1to4-partitions <0|1>     # 1:4/4:1 partitions (default: 1)
-enable-ab-partitions <0|1>       # AB shape partitions (default: 1)
```

**Intra Prediction:**
```bash
-enable-angle-delta <0|1>         # Angle delta intra (default: 1)
-enable-cfl-intra <0|1>           # Chroma from luma (default: 1)
-enable-filter-intra <0|1>        # Filter intra (default: 1)
-enable-intra-edge-filter <0|1>   # Intra edge filter (default: 1)
-enable-smooth-intra <0|1>        # Smooth intra mode (default: 1)
-enable-paeth-intra <0|1>         # Paeth predictor (default: 1)
```

**Palette:**
```bash
-enable-palette <0|1>   # Palette prediction (default: 1)
```

**Transform:**
```bash
-enable-flip-idtx <0|1>           # Extended transforms (default: 1)
-enable-tx64 <0|1>                # 64-pt transform (default: 1)
-reduced-tx-type-set <0|1>        # Reduced transform set (default: 0)
-use-intra-dct-only <0|1>         # DCT only for INTRA (default: 0)
-use-inter-dct-only <0|1>         # DCT only for INTER (default: 0)
-use-intra-default-tx-only <0|1>  # Default TX for INTRA (default: 0)
```

**Motion Vectors:**
```bash
-enable-ref-frame-mvs <0|1>       # Temporal MV prediction (default: 1)
```

**References:**
```bash
-enable-reduced-reference-set <0|1>  # Reduced ref set (default: 0)
```

**Compound Prediction:**
```bash
-enable-obmc <0|1>                # Overlapped block MC (default: 1)
-enable-dual-filter <0|1>         # Dual filter (default: 1)
-enable-diff-wtd-comp <0|1>       # Difference-weighted (default: 1)
-enable-dist-wtd-comp <0|1>       # Distance-weighted (default: 1)
-enable-onesided-comp <0|1>       # One-sided compound (default: 1)
-enable-interinter-wedge <0|1>    # Interinter wedge (default: 1)
-enable-interintra-wedge <0|1>    # Interintra wedge (default: 1)
-enable-masked-comp <0|1>         # Masked compound (default: 1)
-enable-interintra-comp <0|1>     # Interintra compound (default: 1)
-enable-smooth-interintra <0|1>   # Smooth interintra (default: 1)
```

**Advanced Parameters:**
```bash
-aom-params <key=value:...>  # Direct libaom options
```

**Common aom-params:**
```
tune=psnr|ssim
enable-tpl-model=0|1
sharpness=0-7
max-partition-size=8|16|32|64|128
min-partition-size=4|8|16|32|64
quant-b-adapt=0|1
enable-qm=0|1
qm-min=0-15
qm-max=0-15
enable-chroma-deltaq=0|1
enable-keyframe-filtering=0|1|2
kf-max-dist=<int>
kf-min-dist=<int>
enable-order-hint=0|1
enable-ref-frame-mvs=0|1
enable-superres=0|1
superres-mode=0|1|2|3
superres-scale-denominator=8-16
superres-qthresh=1-63
enable-overlay=0|1
```

#### libvpx (VP9) - EXHAUSTIVE OPTIONS

**Rate Control:**
```bash
-b:v <bitrate>          # Target bitrate
-crf <0-63>             # Constant quality (31=default)
-qmin <0-63>            # Minimum quantizer
-qmax <0-63>            # Maximum quantizer
-minrate <bitrate>      # Minimum bitrate
-maxrate <bitrate>      # Maximum bitrate (CBR when minrate=maxrate=b)
-bufsize <size>         # Rate control buffer
```

**Quality/Speed:**
```bash
-quality <best|good|realtime>  # Deadline mode
-deadline <best|good|realtime> # Same as quality
-cpu-used <-8-8>        # Speed setting (higher=faster, VP9: 0-5 typical)
-speed <int>            # Alias for cpu-used
```

**VP9-Specific:**
```bash
-lossless <0|1>         # Lossless mode
-tile-columns <0-6>     # log2 of tile columns
-tile-rows <0-6>        # log2 of tile rows
-frame-parallel <0|1>   # Frame parallel decoding
-aq-mode <0-4>          # 0=off, 1=variance, 2=complexity, 3=cyclic, 4=equator360
-row-mt <0|1>           # Row-based multi-threading
-tune-content <0-2>     # 0=default, 1=screen, 2=film
-corpus-complexity <0-10000>  # Corpus VBR mode (0=standard VBR)
-enable-tpl <0|1>       # Temporal dependency model
```

**VP8-Specific:**
```bash
-screen-content-mode <0-2>  # 0=off, 1=screen, 2=aggressive
```

**Common Options:**
```bash
-g <int>                # GOP size (keyframe interval)
```

**Alternate Reference:**
```bash
-auto-alt-ref <0-2>     # 0=off, 1=on, 2=multi-layer (VP9)
-arnr-maxframes <int>   # ARF max frames
-arnr-type <backward|forward|centered>  # ARF type
-arnr-strength <0-6>    # ARF filter strength
```

**Lookahead:**
```bash
-lag-in-frames <0-25>   # Lookahead frames
-rc-lookahead <0-25>    # Alias for lag-in-frames
```

**Golden Frame:**
```bash
-min-gf-interval <int>  # Min golden/alt-ref interval (VP9)
```

**Error Resilience:**
```bash
-error-resilient <int>  # Enable error resilience
```

**Sharpness:**
```bash
-sharpness <0-7>        # Sharpness setting
```

**Rate Control:**
```bash
-undershoot-pct <0-100> # Undershoot %
-overshoot-pct <0-100>  # Overshoot %
```

**Static Threshold:**
```bash
-static-thresh <int>    # Block skip threshold
```

**Max I-frame Bitrate:**
```bash
-max-intra-rate <0-INT_MAX>  # Max I-frame bitrate %
```

**Slices:**
```bash
-slices <1-8>           # Number of token partitions (log2)
```

**Noise Reduction:**
```bash
-nr <0-INT_MAX>         # Noise sensitivity
```

**Colorspace:**
```bash
-colorspace <space>     # rgb, bt709, unspecified, bt470bg, smpte170m, smpte240m, bt2020_ncl
```

**Temporal Scalability:**
```bash
-ts-parameters <params>  # Temporal scalability config
```

**Reference Frame Control (Advanced):**
```bash
-ref-frame-config <params>  # Per-frame reference control (VP9)
```

**Forced Keyframes:**
```bash
-force_key_frames <expr>  # Force keyframe expression
```

### VIDEO DECODER OPTIONS

#### AV1 Decoder
```bash
-operating_point <0-31>  # Scalable AV1 operating point (default: 0)
```

#### HEVC Decoder (MV-HEVC)
```bash
-view_ids <list>         # View IDs to output (-1 = all views)
-view_ids_available      # Read-only: available view IDs
-view_pos_available      # Read-only: view positions
```

#### rawvideo Decoder
```bash
-top <-1|0|1>           # Field type: -1=progressive, 0=BFF, 1=TFF
```

#### libdav1d (AV1 Decoder)
```bash
-max_frame_delay <int>  # Max internal buffer frames (0=auto)
-filmgrain <0|1>        # Apply film grain (deprecated)
-oppoint <0-31>         # Operating point (default: library default)
-alllayers <0|1>        # Output all spatial layers (default: 0)
```

#### libuavs3d (AVS3 Decoder)
```bash
-frame_threads <int>    # Frame threads (0=auto)
```

#### libxevd (EVC Decoder)
```bash
-threads <int>          # Number of threads
```

#### QSV Decoders
```bash
-async_depth <int>      # Internal parallelization depth
-gpu_copy <default|on|off>  # GPU-accelerated copy
```

**HEVC QSV:**
```bash
-load_plugin <none|hevc_sw|hevc_hw>  # User plugin
-load_plugins <uids>    # Colon-separated plugin UIDs
```

#### v210 Decoder
```bash
-custom_stride <int>    # Line size in bytes (0=auto, -1=strideless)
```

### AUDIO DECODER OPTIONS

#### AC-3 Decoder
```bash
-drc_scale <float>      # Dynamic Range Scale Factor (default: 1.0)
                        # 0=disabled, 0-1=fraction, >1=enhanced
```

#### FLAC Decoder
```bash
-use_buggy_lpc <0|1>    # Use old buggy LPC logic for compatibility
```

#### iLBC Decoder
```bash
-enhance <0|1>          # Audio enhancement (default: 0)
```

### SUBTITLE DECODER OPTIONS

#### libaribb24
```bash
-aribb24-base-path <path>         # Base path for configs/images
-aribb24-skip-ruby-text <0|1>     # Skip ruby text (default: 1)
```

#### libaribcaption
```bash
-sub_type <bitmap|ass|text>       # Subtitle format (default: ass)
-caption_encoding <auto|jis|utf8|latin>  # Text encoding (default: auto)
-font <name1,name2,...>           # Font family names
-ass_single_rect <0|1>            # Single ASS rectangle (default: 0)
-force_outline_text <0|1>         # Always render outline (default: 0)
-outline_width <0.0-3.0>          # Outline width (default: 1.5)
-ignore_background <0|1>          # Ignore background (default: 0)
-ignore_ruby <0|1>                # Ignore ruby characters (default: 0)
-replace_drcs <0|1>               # Replace DRCS as Unicode (default: 1)
-replace_msz_ascii <0|1>          # Replace MSZ fullwidth ASCII (default: 1)
-replace_msz_japanese <0|1>       # Replace MSZ Japanese chars (default: 1)
-replace_msz_glyph <0|1>          # Replace MSZ with halfwidth glyphs (default: 1)
-canvas_size <WxH>                # Canvas resolution for rendering
```

#### dvbsub
```bash
-compute_clut <-2|-1|0|1>  # CLUT computation mode
                           # -2=once if no stream CLUT
                           # -1=if no stream CLUT
                           # 0=never, 1=always override
-dvb_substream <int>       # DVB substream selection (-1=all, default)
```

#### dvdsub
```bash
-palette <16x24bit_hex>    # Global palette (comma-separated hex)
-ifo_palette <filename>    # IFO file for palette (experimental)
-forced_subs_only <0|1>    # Only decode forced subtitles (default: 0)
```

#### libzvbi-teletext
```bash
-txt_page <*|subtitle|page_numbers>  # Pages to decode (default: *)
-txt_default_region <0-87>  # Default character set (-1=no override)
-txt_chop_top <0|1>         # Discard top line (default: 1)
-txt_format <bitmap|text|ass>  # Output format (default: bitmap)
-txt_left <int>             # X offset of bitmaps (default: 0)
-txt_top <int>              # Y offset of bitmaps (default: 0)
-txt_chop_spaces <0|1>      # Remove empty lines/spaces (default: 1)
-txt_duration <ms>          # Display duration (-1=infinity, default)
-txt_transparent <0|1>      # Transparent background (default: 0)
-txt_opacity <0-255>        # Background opacity (0 if transparent, else 255)
```

### SUBTITLE ENCODER OPTIONS

#### dvbsub Encoder
```bash
-min_bpp <2|4|8>        # Minimum bits-per-pixel (default: 4)
```

#### dvdsub Encoder
```bash
-palette <16x24bit_hex>  # Global palette (comma-separated hex)
-even_rows_fix <0|1>     # Make rows even (default: 0)
```

#### LRC Encoder
```bash
-precision <int>         # Fractional timestamp precision (default: 2 = centiseconds)
```

### GLOBAL CODEC OPTIONS

**Generic Options (Apply to Multiple Codecs):**

```bash
# Bitrate
-b:v <bitrate>          # Video bitrate (bits/s, default: 200k)
-ab <bitrate>           # Audio bitrate (bits/s, default: 128k)
-bt <bitrate>           # Video bitrate tolerance (1-pass mode)

# Flags
-flags <flags>          # Generic flags:
                        # mv4, qpel, loop, qscale, pass1, pass2, gray
                        # psnr, truncated, drop_changed, ildct, low_delay
                        # global_header, bitexact, aic, ilme, cgop, output_corrupt

# Time Base
-time_base <rational>   # Codec time base (1/framerate for fixed fps)

# GOP
-g <int>                # GOP size (default: 12)

# Audio
-ar <Hz>                # Audio sample rate
-ac <int>               # Audio channels
-cutoff <Hz>            # Cutoff bandwidth (encoder-specific)
-frame_size <int>       # Audio frame size (samples per channel)

# Quantization
-qcomp <float>          # Video quantizer compression (VBR, 0.0-1.0)
-qblur <float>          # Video quantizer blur (VBR)
-qmin <int>             # Min video quantizer (-1 to 69, default: 2)
-qmax <int>             # Max video quantizer (-1 to 1024, default: 31)
-qdiff <int>            # Max quantizer difference

# B-frames
-bf <int>               # Max B-frames (-1=auto, 0=disabled, default: 0)
-b_qfactor <float>      # QP factor between P and B frames
-b_qoffset <float>      # QP offset between P and B frames

# Rate Control
-maxrate <bitrate>      # Max bitrate (requires bufsize)
-minrate <bitrate>      # Min bitrate (CBR setup)
-bufsize <size>         # Rate control buffer size (bits)
-rc_init_occupancy <int> # RC buffer bits before decode starts

# I-frames
-i_qfactor <float>      # QP factor between P and I frames
-i_qoffset <float>      # QP offset between P and I frames

# DCT
-dct <auto|fastint|int|mmx|altivec|faan>  # DCT algorithm

# Masking
-lumi_mask <float>      # Compress bright areas stronger
-tcplx_mask <float>     # Temporal complexity masking
-scplx_mask <float>     # Spatial complexity masking
-p_mask <float>         # Inter masking
-dark_mask <float>      # Compress dark areas stronger

# IDCT
-idct <auto|int|simple|...>  # IDCT implementation

# Error Handling
-ec <flags>             # Error concealment: guess_mvs, deblock, favor_inter
-err_detect <flags>     # Error detection: crccheck, bitstream, buffer,
                        # explode, ignore_err, careful, compliant, aggressive

# Aspect Ratio
-aspect <ratio>         # Sample aspect ratio
-sar <ratio>            # Sample aspect ratio (alias)

# Debug
-debug <flags>          # Debug info: pict, rc, bitstream, mb_type, qp,
                        # dct_coeff, green_metadata, skip, startcode, er,
                        # mmco, bugs, buffers, thread_ops, nomc

# Threading
-threads <int>          # Number of threads (0=auto)
-thread_type <slice|frame>  # Multi-threading method
-slices <int>           # Number of slices (parallel encoding)

# Color
-color_primaries <primaries>  # bt709, bt470m, bt470bg, smpte170m,
                              # smpte240m, film, bt2020, smpte428,
                              # smpte431, smpte432, jedec-p22
-color_trc <trc>        # bt709, gamma22, gamma28, smpte170m, smpte240m,
                        # linear, log, iec61966-2-4, bt1361, iec61966-2-1,
                        # bt2020_10, bt2020_12, smpte2084, smpte428, arib-std-b67
-colorspace <space>     # rgb, bt709, fcc, bt470bg, smpte170m, smpte240m,
                        # ycocg, bt2020nc, bt2020c, smpte2085,
                        # chroma-derived-nc, chroma-derived-c, ictcp
-color_range <range>    # tv/mpeg/limited (219*2^(n-8))
                        # pc/jpeg/full (2^n-1)
-chroma_sample_location <loc>  # left, center, topleft, top,
                               # bottomleft, bottom

# Profile/Level
-profile <profile>      # Encoder profile (codec-specific)
-level <level>          # Encoder level (codec-specific)

# Motion Estimation (Generic)
-dia_size <int>         # Diamond type & size for ME
-last_pred <int>        # Motion predictors from previous frame
-me_range <int>         # Motion vectors range limit (1023 for DivX)
-global_quality <int>   # Global quality (encoding,audio,video)

# Macroblock Decision
-mbd <simple|bits|rd>   # Macroblock decision algorithm

# Skip Frames (Decoding)
-skip_loop_filter <int>
-skip_idct <int>
-skip_frame <none|default|noref|bidir|nokey|nointra|all>

# Lowres (Decoding)
-lowres <0|1|2|3>       # Decode at 1/2, 1/4, 1/8 resolution

# Field Order
-field_order <progressive|tt|bb|tb|bt>

# Alpha
-skip_alpha <0|1>       # Disable alpha processing (default: 0)

# Whitelist
-codec_whitelist <list> # Allowed decoders (comma-separated)

# Max Pixels
-max_pixels <int>       # Maximum pixels per image (OOM protection)

# Cropping
-apply_cropping <0|1>   # Enable cropping (default: 1)

# Compression Level
-compression_level <int> # Generic compression level (codec-specific)
```

---

## APPENDIX: RECOMMENDED ENCODING WORKFLOWS

### Workflow 1: High-Quality Archival

**Video:**
```bash
ffmpeg -i input.mov \
  -c:v ffv1 -level 3 -coder 1 -context 1 -g 1 \
  -slices 24 -slicecrc 1 \
  -c:a flac -compression_level 12 \
  -metadata title="Archival Master" \
  archive.mkv
```

### Workflow 2: Web Streaming (Multi-Quality)

**1080p:**
```bash
ffmpeg -i input.mov \
  -c:v libx264 -preset slow -crf 23 -profile:v high -level 4.0 \
  -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 192k \
  output_1080p.mp4
```

**720p:**
```bash
ffmpeg -i input.mov \
  -vf "scale=1280:720" \
  -c:v libx264 -preset slow -crf 23 -profile:v high -level 4.0 \
  -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 128k \
  output_720p.mp4
```

**480p:**
```bash
ffmpeg -i input.mov \
  -vf "scale=854:480" \
  -c:v libx264 -preset medium -crf 23 -profile:v main -level 3.1 \
  -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 128k \
  output_480p.mp4
```

### Workflow 3: Professional Editing (ProRes)

**ProRes 422 HQ:**
```bash
ffmpeg -i input.mp4 \
  -c:v prores_ks -profile:v hq -vendor apl0 \
  -c:a pcm_s24le \
  -ar 48000 \
  editing_master.mov
```

### Workflow 4: Broadcast Delivery (MPEG-TS)

**H.264 CBR:**
```bash
ffmpeg -i input.mov \
  -c:v libx264 -preset medium \
  -b:v 8000k -minrate 8000k -maxrate 8000k -bufsize 16000k \
  -profile:v high -level 4.0 \
  -c:a ac3 -b:a 384k \
  -f mpegts broadcast.ts
```

### Workflow 5: Two-Pass High-Quality Encode

**Pass 1:**
```bash
ffmpeg -i input.mov \
  -c:v libx264 -preset slow -b:v 5000k \
  -pass 1 -passlogfile pass1 \
  -an -f null /dev/null
```

**Pass 2:**
```bash
ffmpeg -i input.mov \
  -c:v libx264 -preset slow -b:v 5000k \
  -pass 2 -passlogfile pass1 \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  output.mp4
```

### Workflow 6: HDR10 Encoding

**HEVC HDR10:**
```bash
ffmpeg -i input_hdr.mov \
  -c:v libx265 -preset slow -crf 18 \
  -pix_fmt yuv420p10le \
  -color_primaries bt2020 \
  -color_trc smpte2084 \
  -colorspace bt2020nc \
  -x265-params "hdr-opt=1:repeat-headers=1:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1):max-cll=1000,400" \
  -c:a copy \
  -tag:v hvc1 \
  output_hdr10.mp4
```

### Workflow 7: Screen Recording (Low Latency)

**H.264 Ultrafast:**
```bash
ffmpeg -f gdigrab -i desktop \
  -c:v libx264 -preset ultrafast -tune zerolatency -crf 23 \
  -c:a aac -b:a 128k \
  screen_recording.mp4
```

### Workflow 8: Animation/Anime

**H.264 Tuned for Animation:**
```bash
ffmpeg -i anime.mkv \
  -c:v libx264 -preset slow -tune animation -crf 18 \
  -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  anime_encoded.mp4
```

### Workflow 9: Hardware-Accelerated (QSV)

**H.264 QSV:**
```bash
ffmpeg -hwaccel qsv -c:v h264_qsv -i input.mp4 \
  -c:v h264_qsv -preset slow -global_quality 23 \
  -c:a aac -b:a 192k \
  output_qsv.mp4
```

### Workflow 10: WebM for Web

**VP9 Two-Pass:**
```bash
# Pass 1
ffmpeg -i input.mp4 \
  -c:v libvpx-vp9 -b:v 2M -deadline good -cpu-used 2 \
  -pass 1 -passlogfile webm_pass \
  -an -f webm /dev/null

# Pass 2
ffmpeg -i input.mp4 \
  -c:v libvpx-vp9 -b:v 2M -deadline good -cpu-used 2 \
  -pass 2 -passlogfile webm_pass \
  -c:a libopus -b:a 128k \
  output.webm
```

---

## QUICK REFERENCE TABLES

### Recommended CRF Values

| Use Case | H.264 | HEVC | AV1 | VP9 |
|----------|-------|------|-----|-----|
| Lossless | 0 | 0 | 0 | 0 |
| Visually Lossless | 15-18 | 18-22 | 15-20 | 15-20 |
| High Quality | 18-23 | 22-28 | 20-30 | 20-30 |
| Standard Quality | 23-28 | 28-32 | 30-40 | 30-40 |
| Low Quality/Bandwidth | 28-35 | 32-38 | 40-50 | 40-50 |
| Acceptable Minimum | 28 | 32 | 40 | 40 |

### Bitrate Guidelines (1080p30)

| Quality | H.264 | HEVC | AV1 | VP9 |
|---------|-------|------|-----|-----|
| Low | 2-3 Mbps | 1-2 Mbps | 0.8-1.5 Mbps | 1-2 Mbps |
| Medium | 4-6 Mbps | 2-4 Mbps | 1.5-3 Mbps | 2-4 Mbps |
| High | 8-12 Mbps | 4-8 Mbps | 3-6 Mbps | 4-8 Mbps |
| Very High | 15-20 Mbps | 10-15 Mbps | 8-12 Mbps | 10-15 Mbps |

### Audio Bitrate Guidelines

| Quality | AAC | Opus | Vorbis | MP3 |
|---------|-----|------|--------|-----|
| Low (Mono Speech) | 32-64 kbps | 24-48 kbps | 48-64 kbps | 64-96 kbps |
| Medium (Stereo) | 96-128 kbps | 64-96 kbps | 96-128 kbps | 128-160 kbps |
| High (Stereo Music) | 192-256 kbps | 128-160 kbps | 160-192 kbps | 192-256 kbps |
| Very High (Stereo) | 256-320 kbps | 192-256 kbps | 256-320 kbps | 320 kbps |
| 5.1 Surround | 384-512 kbps | 256-384 kbps | N/A | N/A |

---

## CONCLUSION

This comprehensive codec reference provides complete coverage of FFmpeg's codec ecosystem as documented in the official ffmpeg-codec documentation file (5,071 lines). Use this guide for professional video export workflows in the TermiVoxed video editor application.

**Key Takeaways:**

1. **Modern Codecs:** Prefer H.264, HEVC, AV1, or VP9 for new projects
2. **CRF Mode:** Use CRF for best quality/size ratio (recommended over bitrate mode)
3. **Hardware Acceleration:** QSV, VAAPI, MediaFoundation provide significant speedups
4. **Lossless Archival:** FFV1 + FLAC in MKV for long-term storage
5. **Web Delivery:** H.264 in MP4 for maximum compatibility, VP9/AV1 in WebM for efficiency
6. **Professional Editing:** ProRes in MOV for maximum quality and compatibility

For the latest updates and detailed parameter documentation, always consult the official FFmpeg documentation and run `ffmpeg -h encoder=<encoder_name>` for codec-specific help.
