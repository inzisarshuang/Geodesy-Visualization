# Bundled Plot Fonts / 内置绘图字体

`Geodesy-Visualization` recursively registers every `.ttf` and `.otf` file in this
directory with Matplotlib at runtime. The fonts do not need to be installed in
the host operating system and travel with the toolbox when it is copied or
cloned.

`Geodesy-Visualization` 会在运行时递归注册本目录中的所有 `.ttf` 和 `.otf` 文件。
这些字体无需安装到宿主操作系统；复制或克隆工具箱时会随库一起迁移。

## Included Families / 包含的字体族

| Family | Faces | Intended use | License |
|---|---:|---|---|
| Liberation Sans | Regular/Bold/Italic/Bold Italic | Arial-compatible plotting | SIL OFL 1.1 |
| Liberation Serif | Regular/Bold/Italic/Bold Italic | Times New Roman-compatible plotting | SIL OFL 1.1 |
| TeX Gyre Heros | Regular/Bold/Italic/Bold Italic | Helvetica-style scientific figures | GUST Font License |
| TeX Gyre Termes | Regular/Bold/Italic/Bold Italic | Times-style scientific figures | GUST Font License |
| STIX Two Text | Regular/Bold/Italic/Bold Italic | Scientific publishing text | SIL OFL 1.1 |
| STIX Two Math | Math | Equations and mathematical symbols | SIL OFL 1.1 |
| Noto Sans SC | Variable weight | Simplified Chinese sans serif | SIL OFL 1.1 |
| Noto Serif SC | Variable weight | Simplified Chinese serif | SIL OFL 1.1 |
| IBM Plex Mono | Regular/Bold/Italic/Bold Italic | Code and monospaced labels | SIL OFL 1.1 |

| 字体族 | 字形 | 主要用途 | 许可证 |
|---|---:|---|---|
| Liberation Sans | 常规/粗体/斜体/粗斜体 | 兼容 Arial 风格的绘图 | SIL OFL 1.1 |
| Liberation Serif | 常规/粗体/斜体/粗斜体 | 兼容 Times New Roman 风格的绘图 | SIL OFL 1.1 |
| TeX Gyre Heros | 常规/粗体/斜体/粗斜体 | Helvetica 风格科研绘图 | GUST Font License |
| TeX Gyre Termes | 常规/粗体/斜体/粗斜体 | Times 风格科研绘图 | GUST Font License |
| STIX Two Text | 常规/粗体/斜体/粗斜体 | 科学出版正文 | SIL OFL 1.1 |
| STIX Two Math | 数学字形 | 公式与数学符号 | SIL OFL 1.1 |
| Noto Sans SC | 可变字重 | 简体中文无衬线字体 | SIL OFL 1.1 |
| Noto Serif SC | 可变字重 | 简体中文衬线字体 | SIL OFL 1.1 |
| IBM Plex Mono | 常规/粗体/斜体/粗斜体 | 代码和等宽标签 | SIL OFL 1.1 |

The Noto SC variable files provide their full weight axes in one file per
family. The complete directory is about 48 MB and no individual file exceeds
GitHub's 100 MB normal-file limit.

Noto SC 可变字体文件在每个字体族的单一文件中提供完整字重轴。整个字体目录约
48 MB，且没有单个文件超过 GitHub 普通文件 100 MB 的限制。

## Selection / 字体选择

Select a family in a time-series configuration file:

在时序配置文件中选择字体族：

```ini
font_family = TeX Gyre Heros
```

or:

或者：

```ini
font_family = TeX Gyre Termes
```

`TeX Gyre Heros` is the Visualization default for Python scientific plots.

`TeX Gyre Heros` 是 Visualization Python 科研绘图的默认字体。

Arial and Times New Roman are not bundled because they are proprietary fonts.
The open font licenses are stored beside the relevant families or at the root
of this directory.

由于 Arial 和 Times New Roman 属于专有字体，本仓库不内置它们。开源字体的
许可证保存在相应字体族目录或本目录根部。

## Sources / 字体来源

- TeX Gyre: CTAN `fonts/tex-gyre/opentype`, version 2.501.
- STIX Two: system package 2.0.2, originally from the STIX Fonts project.
- Noto Sans/Serif SC: Google Fonts variable TTF distributions.
- IBM Plex Mono: official IBM Plex GitHub repository.
- Liberation Fonts: system package 2.1.3.

- TeX Gyre：CTAN `fonts/tex-gyre/opentype`，版本 2.501。
- STIX Two：系统软件包 2.0.2，最初来自 STIX Fonts 项目。
- Noto Sans/Serif SC：Google Fonts 可变 TTF 发行版。
- IBM Plex Mono：IBM Plex 官方 GitHub 仓库。
- Liberation Fonts：系统软件包 2.1.3。
