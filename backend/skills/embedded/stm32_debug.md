---
name: stm32_debug
description: Help debug STM32 firmware, peripherals, clocks, interrupts, and hardware bring-up issues.
triggers:
  - STM32
  - HAL
  - CubeMX
  - interrupt
  - UART
  - ADC
  - 单片机
  - 嵌入式
  - 中断
  - 串口
  - 定时器
  - 调试
---

# STM32 Debug

## Instructions
- Ask for MCU model, clock tree, peripheral configuration, and observed symptoms when missing.
- Check clock enable, GPIO alternate function, interrupt priority, DMA configuration, and error flags.
- Prefer small isolation tests before broad rewrites.
- Distinguish firmware issues from wiring, power, and probe configuration.
