/**
 * 平台特定元数据配置和适配器
 */

export type PlatformKey = "douyin" | "kuaishou" | "xiaohongshu" | "bilibili" | "channels"

/**
 * 平台字段配置
 */
export interface PlatformFieldConfig {
    // 平台名称
    name: string
    // 平台代码
    code: number
    // 字段结构
    fields: {
        // 标题字段配置
        title?: {
            enabled: boolean
            maxLength: number
            placeholder: string
            label: string
        }
        // 描述字段配置
        description?: {
            enabled: boolean
            maxLength?: number
            placeholder: string
            label: string
            supportsHashtags: boolean  // 是否支持话题标签
            supportsNewline: boolean   // 是否支持换行
        }
        // 独立标签字段
        tags?: {
            enabled: boolean
            maxCount?: number
            label: string
        }
        // 合并字段（快手、视频号等）
        combined?: {
            enabled: boolean
            label: string
            placeholder: string
            includesTitle: boolean     // 是否包含标题
            includesDescription: boolean // 是否包含描述
            includesTags: boolean      // 是否包含标签
            format: string             // 格式说明
        }
    }
    // 字段组合方式
    layout: "separate" | "title-description" | "combined" | "title-combined"
}

/**
 * 各平台配置
 */
export const PLATFORM_CONFIGS: Record<PlatformKey, PlatformFieldConfig> = {
    // 抖音：标题 + 简介（简介支持话题标签）
    douyin: {
        name: "抖音",
        code: 3,
        fields: {
            title: {
                enabled: true,
                maxLength: 30,
                placeholder: "填写标题，会更多人看到哦~",
                label: "标题"
            },
            description: {
                enabled: true,
                maxLength: 2000,
                placeholder: "添加作品简介 #话题",
                label: "简介描述",
                supportsHashtags: true,
                supportsNewline: true
            },
            tags: {
                enabled: false,  // 标签集成在描述中
                label: "话题"
            }
        },
        layout: "title-description"
    },

    // 快手：单一输入框（包含标题+描述+标签）
    kuaishou: {
        name: "快手",
        code: 4,
        fields: {
            combined: {
                enabled: true,
                label: "作品描述",
                placeholder: "说点什么...记得添加话题哦 #话题",
                includesTitle: true,
                includesDescription: true,
                includesTags: true,
                format: "标题和描述合并，话题用 # 标记"
            }
        },
        layout: "combined"
    },

    // 小红书：标题 + 描述（描述支持换行和话题）
    xiaohongshu: {
        name: "小红书",
        code: 1,
        fields: {
            title: {
                enabled: true,
                maxLength: 20,
                placeholder: "填写标题会有更多赞哦~",
                label: "标题"
            },
            description: {
                enabled: true,
                maxLength: 1000,
                placeholder: "填写描述，支持换行和 #话题#",
                label: "笔记正文",
                supportsHashtags: true,
                supportsNewline: true
            },
            tags: {
                enabled: false,  // 标签集成在描述中
                label: "话题"
            }
        },
        layout: "title-description"
    },

    // B站：标题 + 简介 + 独立标签
    bilibili: {
        name: "B站",
        code: 5,
        fields: {
            title: {
                enabled: true,
                maxLength: 80,
                placeholder: "填写标题",
                label: "视频标题"
            },
            description: {
                enabled: true,
                maxLength: 2000,
                placeholder: "填写简介",
                label: "简介",
                supportsHashtags: false,
                supportsNewline: true
            },
            tags: {
                enabled: true,
                maxCount: 12,
                label: "标签"
            }
        },
        layout: "separate"
    },

    // 视频号：单一描述框（描述+标签）
    channels: {
        name: "视频号",
        code: 2,
        fields: {
            combined: {
                enabled: true,
                label: "描述",
                placeholder: "说点什么...#话题",
                includesTitle: false,  // 视频号没有独立标题
                includesDescription: true,
                includesTags: true,
                format: "描述和话题合并，话题用 # 标记"
            }
        },
        layout: "title-combined"  // 实际上是纯合并，但为了区分
    }
}

/**
 * 通用元数据结构
 */
export interface MaterialMetadata {
    title?: string
    description?: string
    tags?: string[]
    cover_image?: string | null
    // legacy field name
    coverPath?: string | null
}

/**
 * 平台适配器 - 将通用元数据转换为平台特定格式
 */
export class PlatformMetadataAdapter {
    /**
     * 格式化元数据为平台特定格式
     */
    static format(
        platform: PlatformKey,
        metadata: MaterialMetadata
    ): {
        title?: string
        description?: string
        tags?: string[]
        combinedContent?: string
    } {
        const config = PLATFORM_CONFIGS[platform]
        const { title = "", description = "", tags = [] } = metadata

        switch (config.layout) {
            case "separate":
                // B站：分离的标题、描述、标签
                return {
                    title: this.truncate(title, config.fields.title?.maxLength),
                    description,
                    tags
                }

            case "title-description":
                // 抖音、小红书：标题 + 描述（描述中包含话题）
                const descWithTags = this.mergeDescriptionAndTags(description, tags)
                return {
                    title: this.truncate(title, config.fields.title?.maxLength),
                    description: descWithTags
                }

            case "combined":
                // 快手：全部合并到一个字段
                const combined = this.combineAll(title, description, tags)
                return {
                    combinedContent: combined
                }

            case "title-combined":
                // 视频号：描述+标签合并（无独立标题）
                const descWithTagsOnly = this.mergeDescriptionAndTags(description, tags)
                return {
                    description: descWithTagsOnly
                }

            default:
                return { title, description, tags }
        }
    }

    /**
     * 合并描述和标签
     */
    private static mergeDescriptionAndTags(description: string, tags: string[]): string {
        let result = description.trim()

        if (tags && tags.length > 0) {
            const hashtagsText = tags.map(tag => {
                // 如果标签已经以 # 开头，不重复添加
                return tag.startsWith('#') ? tag : `#${tag}`
            }).join(' ')

            // 如果描述为空，直接使用标签
            if (!result) {
                result = hashtagsText
            } else {
                // 如果描述不为空，在末尾添加标签（如果还没有这些标签）
                if (!result.includes(hashtagsText)) {
                    result = `${result}\n\n${hashtagsText}`
                }
            }
        }

        return result
    }

    /**
     * 合并标题、描述和标签为单一字段（快手用）
     */
    private static combineAll(title: string, description: string, tags: string[]): string {
        const parts: string[] = []

        // 添加标题（如果有）
        if (title && title.trim()) {
            parts.push(title.trim())
        }

        // 添加描述（如果有）
        if (description && description.trim()) {
            parts.push(description.trim())
        }

        // 添加标签
        if (tags && tags.length > 0) {
            const hashtagsText = tags.map(tag =>
                tag.startsWith('#') ? tag : `#${tag}`
            ).join(' ')
            parts.push(hashtagsText)
        }

        return parts.join('\n\n')
    }

    /**
     * 截断文本到指定长度
     */
    private static truncate(text: string, maxLength?: number): string {
        if (!maxLength || text.length <= maxLength) {
            return text
        }
        return text.substring(0, maxLength)
    }

    /**
     * 获取平台字段示例
     */
    static getExample(platform: PlatformKey): MaterialMetadata {
        const config = PLATFORM_CONFIGS[platform]

        switch (platform) {
            case "douyin":
                return {
                    title: "精彩瞬间｜这才是生活该有的样子",
                    description: "分享日常生活的美好瞬间，记录每一个值得纪念的时刻",
                    tags: ["生活记录", "vlog", "日常分享"]
                }

            case "kuaishou":
                return {
                    title: "今天的生活太精彩了",
                    description: "和大家分享一下今天发生的有趣事情",
                    tags: ["生活", "分享", "快乐"]
                }

            case "xiaohongshu":
                return {
                    title: "生活小确幸｜值得分享",
                    description: "记录生活中那些让人开心的小瞬间\n\n每一天都要认真生活哦",
                    tags: ["生活方式", "日常", "分享欲"]
                }

            case "bilibili":
                return {
                    title: "【生活vlog】记录日常的点点滴滴",
                    description: "这是一个关于生活的视频\n希望大家喜欢",
                    tags: ["生活", "vlog", "日常", "记录"]
                }

            case "channels":
                return {
                    description: "分享生活中的美好瞬间\n\n每一天都值得被记录",
                    tags: ["生活", "记录", "分享"]
                }

            default:
                return {}
        }
    }

    /**
     * 验证元数据是否符合平台要求
     */
    static validate(
        platform: PlatformKey,
        metadata: MaterialMetadata
    ): { valid: boolean; errors: string[] } {
        const config = PLATFORM_CONFIGS[platform]
        const errors: string[] = []

        // 验证标题长度
        if (config.fields.title?.enabled) {
            const maxLength = config.fields.title.maxLength
            if (metadata.title && metadata.title.length > maxLength) {
                errors.push(`标题超出最大长度限制 (${maxLength}字)`)
            }
        }

        // 验证描述长度
        if (config.fields.description?.enabled) {
            const maxLength = config.fields.description.maxLength
            if (maxLength && metadata.description && metadata.description.length > maxLength) {
                errors.push(`描述超出最大长度限制 (${maxLength}字)`)
            }
        }

        // 验证标签数量
        if (config.fields.tags?.enabled) {
            const maxCount = config.fields.tags.maxCount
            if (maxCount && metadata.tags && metadata.tags.length > maxCount) {
                errors.push(`标签数量超出限制 (最多${maxCount}个)`)
            }
        }

        return {
            valid: errors.length === 0,
            errors
        }
    }
}

/**
 * 获取平台字段提示信息
 */
export function getPlatformFieldHints(platform: PlatformKey): {
    title?: string
    description?: string
    tags?: string
} {
    const config = PLATFORM_CONFIGS[platform]

    switch (config.layout) {
        case "separate":
            return {
                title: "标题将作为独立字段填写",
                description: "描述将作为独立字段填写",
                tags: "标签将作为独立字段填写"
            }

        case "title-description":
            return {
                title: "标题将填写到标题字段",
                description: "描述和标签将合并填写到描述字段",
                tags: "标签将自动添加 # 符号并附加到描述末尾"
            }

        case "combined":
            return {
                title: "标题、描述、标签将合并填写到同一字段",
                description: "内容将按：标题 → 描述 → 标签 的顺序组合",
                tags: "标签将自动添加 # 符号"
            }

        case "title-combined":
            return {
                description: "描述和标签将合并填写",
                tags: "标签将自动添加 # 符号并附加到描述末尾"
            }

        default:
            return {}
    }
}
