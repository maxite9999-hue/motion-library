# 3个可套用动效

用户只需复制编号，并提供文案；无需手工编辑参数。模板表：templates.json。动画实现：templates.mjs。首页默认播放修改了内容的中文示例。

## 接到编号后的执行流程（给处理视频的助手）

1. 读取本站 templates.json，按 exact ID 匹配，不凭聊天记忆猜效果。仅 JJ-012、JJ-019、JJ-026 在本次完成了参数化实现。
2. 下载 templates-source.zip，检查源文件。使用 templates.mjs 导出的 specs、validate、renderSVG；不要把原片视频当作可编辑组件。
3. 将用户文案映射到对应结构，保持意思；不要要求用户自己改 JSON。只有确实缺少必要数字/素材时才询问，不捏造事实。
4. JJ-012 接受 income、currency、rateUnit、incomeLabel、hours、hoursLabel、periodLabel、years、yearsLabel、target。数字范围0–999，目标金额字符串最长16字符。模板只是视觉表达，不替用户推算收益或理财结果。
5. JJ-019 接受 headline、line2、connector、line3。保持三行短语结构；长文案先概括，必要时拆句。中文建议每行2–8字。
6. JJ-026 接受 lines，必须3句。中文建议每句不超过22字。保留三行淡入时间。
7. 30fps，1280×720。使用 renderSVG(id,frame,options,{gold}) 逐帧生成，gold 为 gold-plate.jpg 的 data URL。正文是SVG文字/几何，不是原片截图。
8. 将对应 ID-template.m4a 从0秒起同步附加；不要移位、丢失黑场或默认静音。该文件为原始音乐与音效的混合轨，不是独立分轨，可能包含素材中已有的其他声音。更改节奏必须同步调整声音，不能盲目循环或裁掉尾巴。
9. 已有 Remotion 项目可直接调用 renderSVG；或使用包内 render-template.cjs（需要 Node、React、Remotion bundler/renderer 已安装，并设置 TEMPLATE_RUNTIME 指向其 node_modules）。例如 node render-template.cjs JJ-019 content.json output.mp4。配置由助手生成，不交给用户手工填写。
10. 检查中文字体、文字溢出、画面前后帧、帧数和音轨；生成完给用户预览与文件。

## 保真边界

本批为可编辑初版，不是逐帧完全一致。金色底使用原片无正文时的一张纹理底图，因此动态烟雾不同；可用字体与原字体不同。数字进场、时钟变形是重新绘制的近似运动。保留原片背景署名，不添加新的角标、标题说明或进度条。

模板采用原片的图形主体范围，而不是含前后无关实拍的整段参考模块。JJ-012保留数字到时钟到金额和缩小退场；JJ-019保留所有词组及整组旋转位移；JJ-026保留黑场与三行淡入。前后实拍镜头由成片剪辑时衔接。

原始参考素材及原音轨来自用户提供的视频，公开发布、转载或商业使用时应确认素材与音乐使用权限。
