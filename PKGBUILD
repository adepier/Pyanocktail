# Maintainer: Bertrand Verdu <Choubidouha At gmail Dot com>
pkgname=pyanocktail-git
pkgver=20140626
pkgrel=1
pkgdesc="A Pianocktail Server In Python using Twisted Git version"
arch=('any')
url="https://github.com/bverdu/Pyanocktail"
license=('LGPL2')
depends=('python2' 'setuptools' 'python2-pyalsa' 'python2-twisted' 'python2-sqlalchemy' 'python2-autobahn' 'i2c-tools')
md5sums=('SKIP')
_gitroot="git://github.com/bverdu/Pyanocktail.git"

build(){
	cd "${srcdir}"
    msg "Connecting to GIT server...."

    if [ ! -d ${pkgname} ]; then
        git clone ${_gitroot} ${pkgname} --depth=1 || return 1
    fi

    cd ${pkgname}
    git pull master || return 1

    msg "GIT checkout done"

    msg "Starting make..."
}

package(){
cd "$srcdir"/"$pkgname"
python2 setup.py install --root="$pkgdir"
#chown -R piano:piano "$pkgdir/usr/share/pianocktail"
#chown -R piano:piano "$pkgdir/etc/pianocktail"
}
 
