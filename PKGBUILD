pkgname=davinci-alac-scripts
pkgver=1.0
pkgrel=1
pkgdesc="Davinci Scripts to convert your footage audio to ALAC (crouch)"
arch=('any')
url="https://github.com/GMDProjectL/davinci-alac-scripts"
license=('MIT')
depends=('python' 'ffmpeg')
makedepends=()
checkdepends=()
optdepends=()
backup=()
options=()
install=
source=(${pkgname}::"git+file://${PWD}")

package() {
    cd "$srcdir"
    export DAS_SCRIPT_DIST="${pkgdir}/opt/resolve/Fusion/Scripts/Utility"
    export DAS_ALAC_CONVERTER_DIST="${pkgdir}/usr/bin"

    mkdir -p "${DAS_SCRIPT_DIST}"
    mkdir -p "${DAS_ALAC_CONVERTER_DISTDAS_SCRIPT_DIST}"

    export AAC2ALACBIN="${DAS_ALAC_CONVERTER_DISTDAS_SCRIPT_DIST}/aac2alac"

    install -Dm644 "$srcdir/${pkgname}/convert_aac_to_alac.py" -t "${DAS_SCRIPT_DIST}/convert_aac_to_alac.py"
    install -Dm644 "$srcdir/${pkgname}/aac2alac.py" -t "${AAC2ALACBIN}"

    chmod +x "${AAC2ALACBIN}"
}