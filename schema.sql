--
-- 文件名: schema.sql
-- 描述: 项目数据库初始化脚本，兼容 MySQL 5.7。
--

-- ----------------------------
-- 全局设置：确保支持中文和Emoji (utf8mb4)
-- ----------------------------
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET COLLATION_CONNECTION = utf8mb4_general_ci;

-- ----------------------------
-- 1. 数据库创建 (如果不存在)
-- ----------------------------
CREATE DATABASE IF NOT EXISTS `parse_ucmao`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_general_ci;

-- 切换到目标数据库
USE `parse_ucmao`;


-- ----------------------------
-- 2. 表结构: `parse_library` (视频库表)
-- ----------------------------
-- 注意: MySQL 5.7 完全支持 CURRENT_TIMESTAMP 作为 datetime 和 timestamp 的默认值和更新触发器。
CREATE TABLE IF NOT EXISTS `parse_library` (
  `video_id` varchar(50) COLLATE utf8mb4_general_ci NOT NULL COMMENT '视频唯一ID，作为主键',
  `platform` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '视频来源平台',
  `title` text COLLATE utf8mb4_general_ci COMMENT '视频标题',
  `cover_url` text COLLATE utf8mb4_general_ci COMMENT '视频封面URL',
  `video_url` text COLLATE utf8mb4_general_ci NOT NULL COMMENT '视频播放URL',
  `score` int(11) DEFAULT '0' COMMENT '视频评分',
  `is_visible` tinyint(1) DEFAULT '1' COMMENT '是否显示给前端 (0:隐藏, 1:显示)',
  `last_user_id` int(11) DEFAULT NULL COMMENT '最后解析该视频的用户ID',
  `create_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`video_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='视频库表';


-- ----------------------------
-- 3. 表结构: `users` (用户表)
-- ----------------------------
-- 注意: JSON 数据类型从 MySQL 5.7.8 开始引入，如果您的 5.7 版本够新，可以使用。
CREATE TABLE IF NOT EXISTS `users` (
  `user_id` int(11) NOT NULL AUTO_INCREMENT COMMENT '用户ID，自增主键',
  `open_id` varchar(100) COLLATE utf8mb4_general_ci NOT NULL COMMENT '微信OpenID，用于唯一标识用户',
  `nickname` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '用户昵称',
  `avatar_url` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '用户头像URL',
  `gender` enum('male','female','unknown') COLLATE utf8mb4_general_ci DEFAULT 'unknown' COMMENT '性别',
  `country` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '国家',
  `province` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '省份',
  `city` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '城市',
  `wechat_id` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '微信号',
  `permissions` json DEFAULT NULL COMMENT '用户权限 (JSON)',
  `video_records` json DEFAULT NULL COMMENT '用户观看记录 (JSON)',
  `status` enum('active','inactive','banned') COLLATE utf8mb4_general_ci DEFAULT 'active' COMMENT '用户状态',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `idx_open_id` (`open_id`) COMMENT 'open_id 唯一索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='用户表';


-- ----------------------------
-- 4. 表结构: `score_config` (积分配置表)
-- ----------------------------
CREATE TABLE IF NOT EXISTS `score_config` (
  `config_key` varchar(50) COLLATE utf8mb4_general_ci NOT NULL COMMENT '配置键名',
  `config_value` int(11) NOT NULL DEFAULT '0' COMMENT '配置分值',
  `config_desc` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '配置描述',
  `is_enabled` tinyint(1) DEFAULT '1' COMMENT '是否启用 (0:禁用, 1:启用)',
  PRIMARY KEY (`config_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='积分配置表';

-- 初始积分数据
INSERT IGNORE INTO `score_config` (`config_key`, `config_value`, `config_desc`) VALUES
('parse', 10, '视频解析成功'),
('shareFriend', 8, '分享给好友'),
('shareTimeline', 12, '分享到朋友圈'),
('videoDownload', 5, '视频下载'),
('imageDownload', 3, '封面下载'),
('copyAllInfo', 4, '复制全部信息'),
('copyTitle', 1, '复制标题'),
('copyCoverUrl', 2, '复制封面链接'),
('copyVideoUrl', 3, '复制视频链接'),
('batchCopyTitle', 1, '批量复制标题'),
('batchCopyImageLink', 1, '批量复制封面链接'),
('batchCopyVideoLink', 1, '批量复制视频链接'),
('batchCopyAllInfo', 2, '批量复制全部信息'),
('validPlay', 1, '有效播放');
