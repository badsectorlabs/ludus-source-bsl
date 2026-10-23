data "http" "kali_weekly_checksums" {
  url = "https://cdimage.kali.org/kali-weekly/SHA256SUMS"
}

locals {
  # Capture groups:
  # [0] SHA-256 hash
  # [1] Full ISO filename
  # [2] Release prefix, e.g. kali-linux-2026-W43
  kali_weekly_matches = regexall(
    "(?m)^([0-9a-fA-F]{64})[ \\t]+\\*?((kali-linux-[0-9]{4}-W[0-9]{2})-installer-netinst-amd64\\.iso)\\r?$",
    data.http.kali_weekly_checksums.body
  )

  # Index matches by release prefix.
  kali_weekly_releases = {
    for match in local.kali_weekly_matches : match[2] => match
  }

  # YYYY-WNN sorts chronologically because year/week have fixed widths.
  kali_release = reverse(sort(keys(local.kali_weekly_releases)))[0]
  kali_iso     = local.kali_weekly_releases[local.kali_release]
}

variable "description" {
  type    = string
  default = "Automatically build the latest weekly release of Kali Linux - 'The most advanced Penetration Testing Distribution'"
}

variable "icon_path" {
  type    = string
  default = "icon.png"
}

# The operating system. Can be wxp, w2k, w2k3, w2k8, wvista, win7, win8, win10, l24 (Linux 2.4), l26 (Linux 2.6+), solaris or other. Defaults to other.
variable "os" {
  type    = string
  default = "l26"
}

variable "vm_cpu_cores" {
  type    = string
  default = "4"
}

variable "vm_disk_size" {
  type    = string
  default = "250G"
}

variable "vm_memory" {
  type    = string
  default = "8192"
}

variable "ssh_password" {
  type    = string
  default = "kali"
}

variable "ssh_username" {
  type    = string
  default = "kali"
}

# This block has to be in each file or packer won't be able to use the variables
variable "proxmox_url" {
  type = string
}
variable "proxmox_host" {
  type = string
}
variable "proxmox_storage_pool" {
  type = string
}
variable "proxmox_storage_format" {
  type = string
}
variable "proxmox_skip_tls_verify" {
  type = bool
}
variable "proxmox_pool" {
  type = string
}
variable "iso_storage_pool" {
  type = string
}
variable "ansible_home" {
  type = string
}
variable "ludus_nat_interface" {
  type = string
}
####

locals {
  template_description = "Kali Linux (weekly) template built ${legacy_isotime("2006-01-02 03:04:05")} username:password => kali:kali"
}

source "proxmox-iso" "kali" {
  boot_command = [
    "<esc><wait>",
    "auto <wait>",
    "console-keymaps-at/keymap=us <wait>",
    "console-setup/ask_detect=false <wait>",
    "debconf/frontend=noninteractive <wait>",
    "debian-installer=en_US <wait>",
    "fb=false <wait>",
    "install <wait>",
    "kbd-chooser/method=us <wait>",
    "keyboard-configuration/xkb-keymap=us <wait>",
    "locale=en_US <wait>",
    "netcfg/get_hostname=kali <wait>",
    "preseed/url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/kali-preseed.cfg <wait>",
    "<enter><wait>"
  ]
  boot_key_interval = "100ms"
  boot_wait         = "15s"
  http_directory    = "./http"

  boot_iso {
    type              = "ide"
    iso_checksum      = "sha256:${local.kali_iso[0]}"
    iso_url           = "https://cdimage.kali.org/kali-weekly/${local.kali_iso[1]}"
    iso_storage_pool  = "${var.iso_storage_pool}"
    iso_download_pve  = true
    unmount           = true
    keep_cdrom_device = false
  }

  communicator    = "ssh"
  cores           = "${var.vm_cpu_cores}"
  cpu_type        = "host"
  scsi_controller = "virtio-scsi-single"
  disks {
    disk_size         = "${var.vm_disk_size}"
    format            = "${var.proxmox_storage_format}"
    storage_pool      = "${var.proxmox_storage_pool}"
    type              = "virtio"
    discard           = true
    io_thread         = true
  }
  pool                     = "${var.proxmox_pool}"
  insecure_skip_tls_verify = "${var.proxmox_skip_tls_verify}"
  memory                   = "${var.vm_memory}"
  network_adapters {
    bridge = "${var.ludus_nat_interface}"
    model  = "virtio"
  }
  node                 = "${var.proxmox_host}"
  os                   = "${var.os}"
  proxmox_url          = "${var.proxmox_url}"
  template_description = "${local.template_description}"
  vm_name              = "${local.kali_release}-x64-desktop-template"
  ssh_password         = "${var.ssh_password}"
  ssh_username         = "${var.ssh_username}"
  ssh_wait_timeout     = "30m"
  task_timeout         = "20m" // On slow disks the imgcopy operation takes > 1m
}

build {
  sources = ["source.proxmox-iso.kali"]

  provisioner "ansible" {
    user               = "${var.ssh_username}"
    use_proxy          = false
    extra_arguments    = ["--extra-vars", "{ansible_python_interpreter: /usr/bin/python3, ansible_password: ${var.ssh_password}, ansible_sudo_pass: ${var.ssh_password}}", "--ssh-extra-args", "-o StrictHostKeyChecking=no"]
    playbook_file      = "./kali.yml"
    ansible_env_vars   = ["ANSIBLE_HOME=${var.ansible_home}", "ANSIBLE_LOCAL_TEMP=${var.ansible_home}/tmp", "ANSIBLE_PERSISTENT_CONTROL_PATH_DIR=${var.ansible_home}/pc", "ANSIBLE_SSH_CONTROL_PATH_DIR=${var.ansible_home}/cp"]
    skip_version_check = true
  }

}
