# Maintainer: Bertrand Verdu <Choubidouha At gmail Dot com>
pkgname=pyanocktail
pkgver=0.1
pkgrel=1
pkgdesc="A Pianocktail Server In Python using Twisted"
arch=('any')
url="https://github.com/bverdu/Pyanocktail"
license=('GPL2')
depends=('setuptools')
source=(https://github.com/bverdu/Pyanocktail/blob/master/$pkgname-$pkgver.tar.bz2)
md5sums=('77b40a0bde4efde95816ed690643d90e')

build() {
    cd "$srcdir"
    python2 setup.py install --root="$pkgdir"
}
 
