#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/sys/printk.h>

/* USART2 是 ST-Link 虚拟串口 */
#define UART_NODE   DT_NODELABEL(usart2)

/* 消息队列：存储从 UART 中断接收到的数据 */
K_MSGQ_DEFINE(uart_msgq, 1, 64, 4);

static const struct device *uart_dev = DEVICE_DT_GET(UART_NODE);

/* UART 接收回调函数 */
static void uart_callback(const struct device *dev, void *user_data)
{
    uint8_t c;
    /* 如果未启用 UART 中断，直接返回 */
    if (!uart_irq_update(dev)) {
        return;
    }
    /* 循环读取 FIFO 中的所有数据 */
    while (uart_irq_rx_ready(dev)) {
        if (uart_fifo_read(dev, &c, 1) == 1) {
            k_msgq_put(&uart_msgq, &c, K_NO_WAIT);
        }
    }
}

void main(void)
{
    uint8_t rx_byte;

    if (!device_is_ready(uart_dev)) {
        printk("UART device not ready!\n");
        return;
    }

    printk("\n========================================\n");
    printk("STM32F411 UART Communication Demo\n");
    printk("========================================\n");
    printk("USART2 (PA2-TX, PA3-RX) @ 115200 bps\n");
    printk("Type something, it will be echoed back.\n");
    printk("========================================\n\n");

    /* 配置 UART 中断回调 */
    uart_irq_callback_user_data_set(uart_dev, uart_callback, NULL);
    /* 使能接收中断 */
    uart_irq_rx_enable(uart_dev);

    printk("UART initialized. Waiting for data...\n");

    /* 定时发送消息的计数器 */
    uint32_t tick_count = 0;

    while (1) {
        /* 非阻塞接收，回显收到的数据 */
        while (k_msgq_get(&uart_msgq, &rx_byte, K_NO_WAIT) == 0) {
            /* 回显收到的字符 */
            uart_poll_out(uart_dev, rx_byte);
        }

        /* 每 5 秒发送一条状态消息 */
        k_sleep(K_MSEC(100));
        tick_count++;

        if (tick_count % 50 == 0) { /* 5 秒 */
            printk("[%u] Hello from STM32F411! UART Demo running...\n",
                   k_uptime_get() / 1000);
        }
    }
}
