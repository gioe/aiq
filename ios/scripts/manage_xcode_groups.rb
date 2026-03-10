#!/usr/bin/env ruby
# Script to manage Xcode group hierarchies in the AIQ project.
# Use this script when you need to create or remove group paths before adding files.
#
# Usage:
#   ruby manage_xcode_groups.rb --create-group <group_path>
#   ruby manage_xcode_groups.rb --remove-group <group_path>
#
# Examples:
#   ruby manage_xcode_groups.rb --create-group AIQ/Features/Auth/Views
#   ruby manage_xcode_groups.rb --create-group AIQ/Features/Onboarding/ViewModels
#   ruby manage_xcode_groups.rb --remove-group AIQ/Features/Auth/Views

require 'xcodeproj'

# Parse options
ascii_mode = ARGV.delete('--ascii') || ENV['CI'] || ENV['TERM'] == 'dumb'

OK   = ascii_mode ? '[OK]'    : '✓'
ERR  = ascii_mode ? '[ERROR]' : '✗'
WARN = ascii_mode ? '[WARN]'  : '⚠'

def usage
  puts "Usage:"
  puts "  ruby manage_xcode_groups.rb --create-group <group_path>"
  puts "  ruby manage_xcode_groups.rb --remove-group <group_path>"
  puts ""
  puts "Examples:"
  puts "  ruby manage_xcode_groups.rb --create-group AIQ/Features/Auth/Views"
  puts "  ruby manage_xcode_groups.rb --remove-group AIQ/Features/Auth/Views"
  puts ""
  puts "Options:"
  puts "  --create-group  Create nested group path (creates all intermediate groups)"
  puts "  --remove-group  Remove an empty group by path (fails if group has children)"
  puts "  --ascii         Use ASCII status symbols instead of Unicode (auto-detected in CI)"
end

# Extract action and group path
create_idx = ARGV.index('--create-group')
remove_idx = ARGV.index('--remove-group')

if create_idx.nil? && remove_idx.nil?
  usage
  exit 1
end

if !create_idx.nil? && !remove_idx.nil?
  puts "#{ERR} Cannot specify both --create-group and --remove-group"
  exit 1
end

action = create_idx ? :create : :remove
group_arg_idx = create_idx || remove_idx
group_path = ARGV[group_arg_idx + 1]

if group_path.nil? || group_path.start_with?('--')
  puts "#{ERR} Missing group path argument"
  usage
  exit 1
end

# Change to the ios directory
Dir.chdir(File.dirname(__FILE__) + '/..')

# Open the Xcode project
project_path = 'AIQ.xcodeproj'
unless File.exist?(project_path)
  puts "#{ERR} Could not find #{project_path}"
  exit 1
end

project = Xcodeproj::Project.open(project_path)

# Split group path into parts
path_parts = group_path.split('/').reject(&:empty?)

if path_parts.empty?
  puts "#{ERR} Empty group path"
  exit 1
end

if action == :create
  # Walk the group hierarchy, creating missing groups along the way
  current_group = project.main_group
  path_parts.each do |part|
    existing = current_group[part]
    if existing
      current_group = existing
    else
      current_group = current_group.new_group(part)
      puts "#{OK} Created group: #{part}"
    end
  end
  puts "#{OK} Group path ready: #{group_path}"

elsif action == :remove
  # Navigate to the parent group
  parent_group = project.main_group
  path_parts[0..-2].each do |part|
    parent_group = parent_group[part]
    if parent_group.nil?
      puts "#{ERR} Group not found: #{group_path}"
      exit 1
    end
  end

  # Find the target group
  target_name = path_parts.last
  target_group = parent_group[target_name]

  if target_group.nil?
    puts "#{WARN} Group not found (already removed?): #{group_path}"
    exit 0
  end

  # Refuse to remove groups with children
  unless target_group.children.empty?
    puts "#{ERR} Group is not empty: #{group_path}"
    puts "  Children: #{target_group.children.map(&:display_name).join(', ')}"
    exit 1
  end

  target_group.remove_from_project
  puts "#{OK} Removed group: #{group_path}"
end

project.save
puts "#{OK} Project saved successfully"
