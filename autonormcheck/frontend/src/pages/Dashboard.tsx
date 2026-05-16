import { useState } from 'react'
import { Link } from 'react-router-dom'

export default function Dashboard() {
  const stats = [
    { name: 'Всего проектов', value: '0', href: '/projects' },
    { name: 'Активные анализы', value: '0', href: '/projects' },
    { name: 'Найдено замечаний', value: '0', href: '/projects' },
    { name: 'Подтверждено', value: '0', href: '/projects' },
  ]

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Панель управления</h1>
      
      <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((item) => (
          <Link
            key={item.name}
            to={item.href}
            className="relative bg-white pt-5 px-4 pb-12 sm:pt-6 sm:px-6 shadow rounded-lg overflow-hidden hover:shadow-md transition-shadow"
          >
            <dt className="text-sm font-medium text-gray-500 truncate">{item.name}</dt>
            <dd className="mt-1 text-3xl font-semibold text-gray-900">{item.value}</dd>
          </Link>
        ))}
      </dl>

      <div className="mt-8 bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Быстрый старт</h2>
        <div className="space-y-4">
          <div className="flex items-start">
            <div className="flex-shrink-0 h-8 w-8 bg-primary-100 rounded-full flex items-center justify-center">
              <span className="text-primary-600 font-bold">1</span>
            </div>
            <div className="ml-4">
              <h3 className="text-sm font-medium text-gray-900">Создайте проект</h3>
              <p className="text-sm text-gray-500">Зарегистрируйте новый проект для анализа документации</p>
            </div>
          </div>
          <div className="flex items-start">
            <div className="flex-shrink-0 h-8 w-8 bg-primary-100 rounded-full flex items-center justify-center">
              <span className="text-primary-600 font-bold">2</span>
            </div>
            <div className="ml-4">
              <h3 className="text-sm font-medium text-gray-900">Загрузите файлы</h3>
              <p className="text-sm text-gray-500">Добавьте PDF или DWG файлы проектной документации</p>
            </div>
          </div>
          <div className="flex items-start">
            <div className="flex-shrink-0 h-8 w-8 bg-primary-100 rounded-full flex items-center justify-center">
              <span className="text-primary-600 font-bold">3</span>
            </div>
            <div className="ml-4">
              <h3 className="text-sm font-medium text-gray-900">Запустите анализ</h3>
              <p className="text-sm text-gray-500">AI-система проверит документацию на соответствие нормам</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
