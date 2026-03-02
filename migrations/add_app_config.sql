-- 榜单总开关：为已有数据库添加 app_config 表
-- 执行方式示例: mysql -u 用户名 -p 数据库名 < migrations/add_app_config.sql
-- 或在你使用的数据库客户端中执行本文件内容

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `app_config` (
  `config_key` varchar(50) COLLATE utf8mb4_general_ci NOT NULL COMMENT '配置键名',
  `config_value` varchar(100) COLLATE utf8mb4_general_ci NOT NULL DEFAULT '1' COMMENT '配置值 (如 1=开 0=关)',
  `config_desc` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '配置描述',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`config_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='应用配置表';

INSERT IGNORE INTO `app_config` (`config_key`, `config_value`, `config_desc`) VALUES
('ranking_enabled', '1', '榜单总开关：1=开启 0=关闭');
