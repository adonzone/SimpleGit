class Simplegit < Formula
  include Language::Python::Virtualenv

  desc "Simplified Git CLI with native .git inspection and interactive terminal UI"
  homepage "https://github.com/AdonZ/SimpleGit"
  url "https://github.com/AdonZ/SimpleGit/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_RELEASE_TARBALL_SHA256"
  license "GPL-3.0-or-later"

  depends_on "git"
  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "SimpleGit", shell_output("#{bin}/sgit --version")
    system "#{bin}/sgit", "init", testpath/"repo"
    assert_predicate testpath/"repo/.git/HEAD", :exist?
  end
end
