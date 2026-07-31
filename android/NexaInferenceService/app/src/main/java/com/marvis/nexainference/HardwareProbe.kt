package com.marvis.nexainference

import android.os.Build

/**
 * 硬件探测：判断是否具备 Qualcomm Hexagon NPU。
 *
 * Nexa SDK 通过 plugin_id 选择硬件后端：
 *   - "npu"  -> Qualcomm Hexagon NPU（仅骁龙设备可用）
 *   - "cpu"  -> 纯 CPU 回退（全部 CPU 模式下运行）
 *   - "gpu"  -> Adreno GPU（可选）
 */
object HardwareProbe {

    /** 是否为高通平台（Hexagon NPU 可用前提）。 */
    fun supportsHexagon(): Boolean {
        val hw = Build.HARDWARE.lowercase()
        val board = Build.BOARD.lowercase()
        return hw.contains("qcom") || board.contains("qcom") ||
                hw.contains("snapdragon") || board.contains("snapdragon")
    }

    /**
     * 解析最终使用的 plugin。
     * 用户偏好为 "npu" 但设备非高通时，自动降级为 "cpu"，保证“全部 CPU 模式下运行”。
     */
    fun resolvePlugin(preferred: String): String {
        return if (preferred == "npu" && supportsHexagon()) "npu" else "cpu"
    }
}
