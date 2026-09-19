/* SignalHound scanner: continuous BLE scan on the nRF5340 (nRF7002-DK), print RSSI of the
 * target beacon (matched by BLE local name) as CSV lines on the console UART (J-Link VCOM).
 *
 *   BOOT,<version>
 *   TARGET,<name>,<rssi>,<addr>
 *   SEEN,<name>,<rssi>              (rate limited, other named advertisers)
 *   SCAN,<packets_total>,<target_total>   (1 Hz heartbeat)
 */
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/hci.h>
#include <zephyr/drivers/gpio.h>
#include <string.h>

#define VERSION "0.1"
#define NAME_MAX 32

static uint32_t packets_total;
static uint32_t target_total;
static int64_t last_seen_report;

#if DT_NODE_EXISTS(DT_ALIAS(led0))
static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios);
#endif

struct name_ctx {
	char name[NAME_MAX];
	bool found;
};

static bool parse_name(struct bt_data *data, void *user_data)
{
	struct name_ctx *ctx = user_data;

	if (data->type == BT_DATA_NAME_COMPLETE || data->type == BT_DATA_NAME_SHORTENED) {
		size_t len = MIN(data->data_len, NAME_MAX - 1);
		memcpy(ctx->name, data->data, len);
		ctx->name[len] = '\0';
		ctx->found = true;
		return false;
	}
	return true;
}

static void scan_cb(const bt_addr_le_t *addr, int8_t rssi, uint8_t adv_type, struct net_buf_simple *buf)
{
	struct name_ctx ctx = { .found = false };
	char addr_str[BT_ADDR_LE_STR_LEN];

	packets_total++;
	bt_data_parse(buf, parse_name, &ctx);
	if (!ctx.found) {
		return;
	}
	if (strcmp(ctx.name, CONFIG_SH_TARGET_NAME) == 0) {
		target_total++;
		bt_addr_le_to_str(addr, addr_str, sizeof(addr_str));
		printk("TARGET,%s,%d,%s\n", ctx.name, rssi, addr_str);
#if DT_NODE_EXISTS(DT_ALIAS(led0))
		gpio_pin_toggle_dt(&led);
#endif
		return;
	}
	int64_t now = k_uptime_get();
	if (now - last_seen_report > CONFIG_SH_SEEN_REPORT_MS) {
		last_seen_report = now;
		printk("SEEN,%s,%d\n", ctx.name, rssi);
	}
}

int main(void)
{
	int err;

#if DT_NODE_EXISTS(DT_ALIAS(led0))
	if (gpio_is_ready_dt(&led)) {
		gpio_pin_configure_dt(&led, GPIO_OUTPUT_INACTIVE);
	}
#endif
	printk("BOOT,%s,target=%s\n", VERSION, CONFIG_SH_TARGET_NAME);

	err = bt_enable(NULL);
	if (err) {
		printk("ERROR,bt_enable,%d\n", err);
		return 0;
	}

	/* Active scan so Android's scan-response (where the name often lives) is captured.
	 * Duplicate filtering OFF: we want every packet's RSSI. Aggressive window for sample rate. */
	struct bt_le_scan_param param = {
		.type = BT_LE_SCAN_TYPE_ACTIVE,
		.options = BT_LE_SCAN_OPT_NONE,
		.interval = BT_GAP_SCAN_FAST_INTERVAL,
		.window = BT_GAP_SCAN_FAST_WINDOW,
	};
	err = bt_le_scan_start(&param, scan_cb);
	if (err) {
		printk("ERROR,scan_start,%d\n", err);
		return 0;
	}

	while (1) {
		k_sleep(K_SECONDS(1));
		printk("SCAN,%u,%u\n", packets_total, target_total);
	}
	return 0;
}
